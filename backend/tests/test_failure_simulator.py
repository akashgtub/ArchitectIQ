"""Unit and integration tests for chaos lab failure simulation and resilience testing."""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.chaos_lab.failure_simulator import FailureSimulator, simulate_failure
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Connection,
    Constraints,
    FailureScenario,
    FailureType,
    PathType,
    WorkloadConfig,
)


@pytest.fixture
def resilient_graph() -> ArchitectureGraph:
    """Fixture providing an architecture with redundant API servers and cache."""
    lb = Component(id="lb-1", type=ComponentType.LOAD_BALANCER, capacity_rps=2500.0, replicas=1)
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0, replicas=3, base_latency_ms=10.0)
    cache = Component(id="cache-1", type=ComponentType.CACHE, capacity_rps=3000.0, replicas=1, base_latency_ms=2.0, cache_hit_ratio=0.85)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=1000.0, replicas=1, base_latency_ms=25.0)

    conns = [
        Connection(source="lb-1", target="api-1", path_type=PathType.BOTH),
        Connection(source="api-1", target="cache-1", path_type=PathType.READ),
        Connection(source="api-1", target="db-1", path_type=PathType.WRITE),
        Connection(source="cache-1", target="db-1", path_type=PathType.READ),
    ]
    return ArchitectureGraph(components=[lb, api, cache, db], connections=conns)


@pytest.fixture
def standard_workload() -> WorkloadConfig:
    return WorkloadConfig(
        requests_per_second=400.0,
        read_ratio=0.8,
        duration_seconds=15.0,
        seed=42,
    )


def test_api_replica_loss_with_redundancy(resilient_graph, standard_workload):
    """Loss of 1 of 3 API replicas should degrade capacity but maintain service via remaining replicas."""
    scenario = FailureScenario(
        name="API Replica Loss",
        failure_type=FailureType.REPLICA_LOSS,
        target_component_id="api-1",
        degradation_factor=1.0,  # Lose 1 replica
        start_time_sec=5.0,
        duration_sec=5.0,
    )

    result = simulate_failure(resilient_graph, standard_workload, scenario)

    assert result.redundancy_supported is True
    assert result.recovery_observed is True
    assert result.failure_metrics.completed_requests > 0
    # Remaining 2 replicas handle 400 RPS comfortably
    assert result.failure_metrics.error_rate < 0.10


def test_api_crash_single_replica_spof(standard_workload):
    """Crash of single-replica API server causes total tier failure and error surge."""
    lb = Component(id="lb-1", type=ComponentType.LOAD_BALANCER, capacity_rps=2000.0)
    api = Component(id="api-single", type=ComponentType.API_SERVER, capacity_rps=500.0, replicas=1)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=500.0)

    conns = [
        Connection(source="lb-1", target="api-single"),
        Connection(source="api-single", target="db-1"),
    ]
    graph = ArchitectureGraph(components=[lb, api, db], connections=conns)

    scenario = FailureScenario(
        name="SPOF API Crash",
        failure_type=FailureType.API_CRASH,
        target_component_id="api-single",
        start_time_sec=2.0,
        duration_sec=8.0,
    )

    result = simulate_failure(graph, standard_workload, scenario)

    assert result.redundancy_supported is False
    assert result.error_rate_delta > 0.0
    assert result.failure_metrics.dropped_requests > 0


def test_database_slowdown_impact(resilient_graph, standard_workload):
    """Database slowdown must increase p95 latency compared to baseline."""
    scenario = FailureScenario(
        name="DB Slowdown Spike",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="db-1",
        degradation_factor=4.0,  # 4x latency increase
        start_time_sec=3.0,
        duration_sec=8.0,
    )

    result = simulate_failure(resilient_graph, standard_workload, scenario)

    assert result.latency_delta_ms > 0.0
    assert result.failure_metrics.p95_latency_ms > result.baseline_metrics.p95_latency_ms
    assert "db-1" in result.affected_components


def test_cache_outage_cascades_to_database(resilient_graph, standard_workload):
    """Cache outage forces 100% cache misses, increasing traffic and queueing on downstream DB."""
    scenario = FailureScenario(
        name="Redis Cache Outage",
        failure_type=FailureType.CACHE_OUTAGE,
        target_component_id="cache-1",
        start_time_sec=0.0,
        duration_sec=15.0,  # Persists entire run
    )

    result = simulate_failure(resilient_graph, standard_workload, scenario)

    db_base_offered = result.baseline_metrics.component_breakdown["db-1"].offered_rps
    db_fail_offered = result.failure_metrics.component_breakdown["db-1"].offered_rps

    # DB offered load must be substantially higher during cache outage
    assert db_fail_offered > db_base_offered
    assert "cache-1" in result.affected_components


def test_traffic_spike_scenario(resilient_graph, standard_workload):
    """Traffic spike scenario surges global load and increases completed or queued traffic."""
    scenario = FailureScenario(
        name="Black Friday Traffic Spike",
        failure_type=FailureType.TRAFFIC_SPIKE,
        target_component_id=None,
        degradation_factor=2.5,  # 2.5x traffic surge
        start_time_sec=5.0,
        duration_sec=5.0,
    )

    result = simulate_failure(resilient_graph, standard_workload, scenario)

    # Spike increases total requests
    total_base = result.baseline_metrics.completed_requests + result.baseline_metrics.dropped_requests
    total_fail = result.failure_metrics.completed_requests + result.failure_metrics.dropped_requests
    assert total_fail > total_base


def test_invalid_target_component_raises_error(resilient_graph, standard_workload):
    """Non-existent target component ID must be rejected with ValueError."""
    scenario = FailureScenario(
        name="Invalid Target",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="ghost-db-node",
    )

    with pytest.raises(ValueError, match="not found in architecture"):
        FailureSimulator(resilient_graph, standard_workload, scenario)


def test_negative_degradation_factor_rejected():
    """Negative degradation factor must be rejected by schema."""
    with pytest.raises(ValidationError):
        FailureScenario(
            name="Negative Factor",
            failure_type=FailureType.DB_SLOWDOWN,
            target_component_id="db-1",
            degradation_factor=-2.0,
        )


def test_architecture_immutability(resilient_graph, standard_workload):
    """Failure simulation must never mutate the caller's original architecture graph."""
    original_api_replicas = resilient_graph.get_component("api-1").replicas
    original_db_latency = resilient_graph.get_component("db-1").base_latency_ms

    scenario = FailureScenario(
        name="DB Slowdown",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="db-1",
        degradation_factor=5.0,
    )

    simulate_failure(resilient_graph, standard_workload, scenario)

    assert resilient_graph.get_component("api-1").replicas == original_api_replicas
    assert resilient_graph.get_component("db-1").base_latency_ms == original_db_latency


def test_deterministic_failure_simulation(resilient_graph, standard_workload):
    """Repeated failure simulation with identical seed must produce identical metrics."""
    scenario = FailureScenario(
        name="Reproducible DB Slowdown",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="db-1",
        degradation_factor=3.0,
        start_time_sec=4.0,
        duration_sec=6.0,
    )

    res1 = simulate_failure(resilient_graph, standard_workload, scenario)
    res2 = simulate_failure(resilient_graph, standard_workload, scenario)

    assert res1.latency_delta_ms == res2.latency_delta_ms
    assert res1.throughput_delta_rps == res2.throughput_delta_rps
    assert res1.error_rate_delta == res2.error_rate_delta
    assert res1.failure_metrics.p95_latency_ms == res2.failure_metrics.p95_latency_ms


def test_resilience_scenario_json_file(resilient_graph):
    """Verify backend/examples/resilience_scenario.json loads and runs cleanly."""
    path = Path(__file__).resolve().parent.parent / "examples" / "resilience_scenario.json"
    assert path.exists()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenario = FailureScenario(**data["scenario"])
    wl = WorkloadConfig(**data["workload"])
    wl.duration_seconds = 10.0  # Fast test duration

    res = simulate_failure(resilient_graph, wl, scenario)
    assert res.status in ("success", "degraded", "failed")
    assert len(res.resilience_summary) > 0
