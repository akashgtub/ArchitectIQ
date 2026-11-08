"""Integration and unit tests for the baseline simulation engine."""

import json
import math
from pathlib import Path
import pytest

from backend.simulator.engine import SimulationEngine, SimulationError
from backend.simulator.performance import calculate_latencies, evaluate_constraints
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Connection,
    Constraints,
    PathType,
    PerformanceMetrics,
    SeverityLevel,
    WorkloadConfig,
    WorkloadPattern,
)


@pytest.fixture
def sample_architecture_fixture() -> tuple[ArchitectureGraph, WorkloadConfig, Constraints]:
    """Load the sample architecture JSON fixture."""
    path = Path(__file__).resolve().parent.parent / "examples" / "sample_architecture.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return (
        ArchitectureGraph(**data["architecture"]),
        WorkloadConfig(**data["workload"]),
        Constraints(**data["constraints"]),
    )


def test_sample_architecture_simulation_runs(sample_architecture_fixture):
    """Verify end-to-end simulation runs on the realistic sample architecture."""
    graph, workload, constraints = sample_architecture_fixture
    # Use shorter duration for fast test execution
    workload.duration_seconds = 10.0

    engine = SimulationEngine(graph=graph, workload=workload, constraints=constraints)
    result = engine.run()

    assert result.status in ("success", "degraded")
    assert result.simulation_type == "baseline"
    assert result.metrics.completed_requests > 0
    assert result.metrics.throughput_rps > 0.0
    assert result.metrics.p50_latency_ms > 0.0
    assert result.metrics.p95_latency_ms >= result.metrics.p50_latency_ms
    assert result.metrics.p99_latency_ms >= result.metrics.p95_latency_ms
    assert result.metrics.total_monthly_cost_usd > 0.0
    assert len(result.assumptions) > 0
    assert result.simulation_metadata["method"] == "discrete_event_queueing"


def test_disconnected_graph_raises_simulation_error():
    """Unreachable or disconnected components must be rejected with SimulationError."""
    c1 = Component(id="lb-1", type=ComponentType.LOAD_BALANCER, capacity_rps=1000.0)
    c2 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    c3 = Component(id="isolated-db", type=ComponentType.DATABASE, capacity_rps=500.0)

    # c3 has no connections to/from anything
    conn = Connection(source="lb-1", target="api-1")
    graph = ArchitectureGraph(components=[c1, c2, c3], connections=[conn])
    workload = WorkloadConfig(requests_per_second=100.0, duration_seconds=5.0)

    with pytest.raises(SimulationError, match="Isolated / unreachable components detected"):
        SimulationEngine(graph, workload)


def test_cache_hits_reduce_database_traffic():
    """High cache hit ratio must significantly reduce read load on downstream database."""
    lb = Component(id="lb", type=ComponentType.LOAD_BALANCER, capacity_rps=2000.0)
    api = Component(id="api", type=ComponentType.API_SERVER, capacity_rps=1000.0, replicas=2)
    db = Component(id="db", type=ComponentType.DATABASE, capacity_rps=800.0)

    conns = [
        Connection(source="lb", target="api", path_type=PathType.BOTH),
        Connection(source="api", target="cache", path_type=PathType.READ),
        Connection(source="api", target="db", path_type=PathType.WRITE),
        Connection(source="cache", target="db", path_type=PathType.READ),
    ]

    # Setup 1: High cache hit ratio (0.95)
    cache_high = Component(id="cache", type=ComponentType.CACHE, capacity_rps=3000.0, cache_hit_ratio=0.95)
    graph_high = ArchitectureGraph(components=[lb, api, cache_high, db], connections=conns)
    wl_high = WorkloadConfig(requests_per_second=400.0, read_ratio=0.9, duration_seconds=10.0, seed=42)
    res_high = SimulationEngine(graph_high, wl_high).run()

    # Setup 2: Low cache hit ratio (0.05)
    cache_low = Component(id="cache", type=ComponentType.CACHE, capacity_rps=3000.0, cache_hit_ratio=0.05)
    graph_low = ArchitectureGraph(components=[lb, api, cache_low, db], connections=conns)
    wl_low = WorkloadConfig(requests_per_second=400.0, read_ratio=0.9, duration_seconds=10.0, seed=42)
    res_low = SimulationEngine(graph_low, wl_low).run()

    db_offered_high = res_high.metrics.component_breakdown["db"].offered_rps
    db_offered_low = res_low.metrics.component_breakdown["db"].offered_rps

    # When cache hit ratio is high, DB receives substantially less traffic than when cache hit is low
    assert db_offered_high < db_offered_low
    # Also overall latency is lower with high cache hits
    assert res_high.metrics.mean_latency_ms < res_low.metrics.mean_latency_ms


def test_capacity_bottleneck_detection_under_overload():
    """Overloading a component must increase utilization and flag a critical bottleneck."""
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=200.0, replicas=1)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=1000.0)
    conn = Connection(source="api-1", target="db-1")
    graph = ArchitectureGraph(components=[api, db], connections=[conn])

    # Run with 100 RPS: within capacity (utilization ~0.50)
    wl_normal = WorkloadConfig(requests_per_second=100.0, duration_seconds=10.0, seed=42)
    res_normal = SimulationEngine(graph, wl_normal).run()
    assert res_normal.metrics.component_breakdown["api-1"].is_bottleneck is False

    # Run with 500 RPS: exceeds 200 RPS capacity
    wl_overload = WorkloadConfig(requests_per_second=500.0, duration_seconds=10.0, seed=42)
    res_overload = SimulationEngine(graph, wl_overload).run()

    api_metrics = res_overload.metrics.component_breakdown["api-1"]
    assert api_metrics.utilization > 1.0
    assert api_metrics.is_bottleneck is True
    assert any(b.component_id == "api-1" and b.severity == SeverityLevel.CRITICAL for b in res_overload.bottlenecks)


def test_replica_scaling_improves_capacity():
    """Adding replicas must increase effective capacity and eliminate bottleneck under load."""
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=2000.0)

    # 1 replica: capacity = 400 RPS
    api_single = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=400.0, replicas=1)
    graph_single = ArchitectureGraph(components=[api_single, db], connections=[Connection(source="api-1", target="db-1")])

    # 3 replicas: capacity = 1200 RPS
    api_scaled = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=400.0, replicas=3)
    graph_scaled = ArchitectureGraph(components=[api_scaled, db], connections=[Connection(source="api-1", target="db-1")])

    # Workload of 800 RPS (overwhelms 1 replica, easily handled by 3)
    wl = WorkloadConfig(requests_per_second=800.0, duration_seconds=10.0, seed=42)

    res_single = SimulationEngine(graph_single, wl).run()
    res_scaled = SimulationEngine(graph_scaled, wl).run()

    # Single replica should be overloaded with high utilization and latency
    assert res_single.metrics.component_breakdown["api-1"].utilization > 1.0
    assert res_single.metrics.component_breakdown["api-1"].is_bottleneck is True

    # Scaled replicas should comfortably handle load
    assert res_scaled.metrics.component_breakdown["api-1"].utilization < 1.0
    assert res_scaled.metrics.component_breakdown["api-1"].is_bottleneck is False
    assert res_scaled.metrics.p95_latency_ms < res_single.metrics.p95_latency_ms


def test_simulation_reproducibility():
    """Identical seed, architecture, and workload must produce 100% identical metrics."""
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0, replicas=2)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=800.0)
    conn = Connection(source="api-1", target="db-1")
    graph = ArchitectureGraph(components=[api, db], connections=[conn])
    wl = WorkloadConfig(requests_per_second=300.0, duration_seconds=10.0, seed=777)

    res1 = SimulationEngine(graph, wl).run()
    res2 = SimulationEngine(graph, wl).run()

    assert res1.metrics.p50_latency_ms == res2.metrics.p50_latency_ms
    assert res1.metrics.p95_latency_ms == res2.metrics.p95_latency_ms
    assert res1.metrics.p99_latency_ms == res2.metrics.p99_latency_ms
    assert res1.metrics.throughput_rps == res2.metrics.throughput_rps
    assert res1.metrics.error_rate == res2.metrics.error_rate
    assert res1.metrics.completed_requests == res2.metrics.completed_requests


def test_calculate_latencies_exact_samples():
    """Verify percentile calculation against known sample array."""
    samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    mean_val, p50_val, p95_val, p99_val = calculate_latencies(samples)

    assert mean_val == 55.0
    assert p50_val == 55.0
    assert p95_val == pytest.approx(95.5, abs=0.5)
    assert p99_val == pytest.approx(99.1, abs=0.5)

    # Empty samples boundary
    assert calculate_latencies([]) == (0.0, 0.0, 0.0, 0.0)


def test_constraint_violations_triggering():
    """Verify hard performance and budget constraints trigger violations properly."""
    metrics = PerformanceMetrics(
        mean_latency_ms=120.0,
        p50_latency_ms=100.0,
        p95_latency_ms=250.0,
        p99_latency_ms=350.0,
        throughput_rps=400.0,
        error_rate=0.08,
        completed_requests=4000,
        dropped_requests=350,
        total_monthly_cost_usd=800.0,
    )

    constraints = Constraints(
        max_p95_latency_ms=200.0,  # Violated (actual: 250)
        monthly_budget_usd=500.0,   # Violated (actual: 800)
        min_throughput_rps=500.0,   # Violated (actual: 400)
        max_error_rate=0.05,        # Violated (actual: 0.08)
    )

    violations = evaluate_constraints(metrics, constraints)
    violation_names = {v.constraint_name for v in violations}

    assert "max_p95_latency_ms" in violation_names
    assert "monthly_budget_usd" in violation_names
    assert "min_throughput_rps" in violation_names
    assert "max_error_rate" in violation_names
    assert len(violations) == 4


def test_zero_traffic_behavior():
    """Verify simulation handles near-zero traffic gracefully without division by zero."""
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=500.0)
    graph = ArchitectureGraph(components=[api, db], connections=[Connection(source="api-1", target="db-1")])

    # Minimal traffic horizon (0.01 RPS over 1 second => 0 requests expected)
    wl = WorkloadConfig(requests_per_second=0.01, duration_seconds=1.0, seed=42)
    res = SimulationEngine(graph, wl).run()

    assert res.metrics.completed_requests >= 0
    assert res.metrics.dropped_requests == 0
    assert res.metrics.error_rate == 0.0
    assert res.metrics.throughput_rps >= 0.0
    # Does not crash or produce NaN
    assert not math.isnan(res.metrics.mean_latency_ms)


def test_throughput_and_error_rate_calculations():
    """Verify throughput and error-rate calculations match exact definitions."""
    from backend.simulator.workload import SimulatedRequest
    from backend.simulator.performance import compile_performance_metrics

    c1 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=100.0)
    graph = ArchitectureGraph(components=[c1], connections=[])

    # 10 requests: 8 completed (latency 25ms each), 2 dropped
    reqs = []
    for i in range(8):
        r = SimulatedRequest(request_id=i, arrival_time=i * 0.1, is_read=True)
        r.mark_completed(total_latency_ms=25.0)
        reqs.append(r)
    for i in range(8, 10):
        r = SimulatedRequest(request_id=i, arrival_time=i * 0.1, is_read=True)
        r.mark_dropped(component_id="api-1", reason="Queue overflow")
        reqs.append(r)

    duration = 2.0  # seconds
    stats = {
        "api-1": {
            "offered_count": 10,
            "completed_count": 8,
            "dropped_count": 2,
            "total_service_ms": 200.0,
            "total_queue_ms": 0.0,
            "mean_queue_depth": 1.0,
        }
    }
    metrics = compile_performance_metrics(reqs, duration, graph, stats)

    # Throughput = 8 completed / 2.0 sec = 4.0 RPS
    assert metrics.throughput_rps == 4.0
    # Error rate = 2 dropped / 10 total = 0.20 (20%)
    assert metrics.error_rate == 0.20
    assert metrics.completed_requests == 8
    assert metrics.dropped_requests == 2
    assert metrics.mean_latency_ms == 25.0
