"""Unit tests for Pydantic v2 schemas and provisional contract models."""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Connection,
    Constraints,
    DEFAULT_COST_PER_MONTH,
    FailureScenario,
    FailureType,
    OptimizationObjective,
    OptimizationRequest,
    PathType,
    WorkloadConfig,
    WorkloadPattern,
)


def test_valid_component_creation():
    """Test valid component creation with defaults."""
    c = Component(
        id="api-1",
        type=ComponentType.API_SERVER,
        capacity_rps=500.0,
        replicas=2,
    )
    assert c.id == "api-1"
    assert c.type == ComponentType.API_SERVER
    assert c.capacity_rps == 500.0
    assert c.replicas == 2
    assert c.base_latency_ms == 5.0
    # Cost should be populated from default tier
    assert c.cost_per_month_usd == DEFAULT_COST_PER_MONTH[ComponentType.API_SERVER]


def test_cache_component_default_hit_ratio():
    """Test cache component automatically receives default hit ratio."""
    cache = Component(
        id="cache-1",
        type=ComponentType.CACHE,
        capacity_rps=2000.0,
    )
    assert cache.cache_hit_ratio == 0.8
    assert cache.cost_per_month_usd == DEFAULT_COST_PER_MONTH[ComponentType.CACHE]


def test_invalid_component_capacity():
    """Component capacity must be strictly positive."""
    with pytest.raises(ValidationError):
        Component(
            id="db-1",
            type=ComponentType.DATABASE,
            capacity_rps=-10.0,
        )


def test_invalid_component_replicas():
    """Replicas must be at least 1."""
    with pytest.raises(ValidationError):
        Component(
            id="api-1",
            type=ComponentType.API_SERVER,
            capacity_rps=100.0,
            replicas=0,
        )


def test_valid_architecture_graph():
    """Test valid graph construction and helper methods."""
    c1 = Component(id="lb-1", type=ComponentType.LOAD_BALANCER, capacity_rps=2000.0)
    c2 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0, replicas=2)
    conn = Connection(source="lb-1", target="api-1", protocol="http")

    graph = ArchitectureGraph(components=[c1, c2], connections=[conn])
    assert len(graph.components) == 2
    assert len(graph.connections) == 1
    assert graph.get_component("lb-1") == c1
    assert graph.get_component("non-existent") is None

    outgoing = graph.get_outgoing_connections("lb-1")
    assert len(outgoing) == 1
    assert outgoing[0].target == "api-1"

    incoming = graph.get_incoming_connections("api-1")
    assert len(incoming) == 1
    assert incoming[0].source == "lb-1"

    entry_points = graph.get_entry_points()
    assert len(entry_points) == 1
    assert entry_points[0].id == "lb-1"


def test_graph_duplicate_component_ids():
    """Graph must reject duplicate component IDs."""
    c1 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    c2 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=600.0)

    with pytest.raises(ValidationError, match="Duplicate component IDs detected"):
        ArchitectureGraph(components=[c1, c2], connections=[])


def test_graph_invalid_connection_source():
    """Connection source must exist in components."""
    c1 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    conn = Connection(source="unknown-node", target="api-1")

    with pytest.raises(ValidationError, match="Connection source 'unknown-node' does not exist"):
        ArchitectureGraph(components=[c1], connections=[conn])


def test_graph_invalid_connection_target():
    """Connection target must exist in components."""
    c1 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    conn = Connection(source="api-1", target="unknown-target")

    with pytest.raises(ValidationError, match="Connection target 'unknown-target' does not exist"):
        ArchitectureGraph(components=[c1], connections=[conn])


def test_graph_self_loop_rejected():
    """Connection cannot have source == target."""
    c1 = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=500.0)
    conn = Connection(source="api-1", target="api-1")

    with pytest.raises(ValidationError, match="Self-loop connection detected"):
        ArchitectureGraph(components=[c1], connections=[conn])


def test_valid_workload_config():
    """Test valid workload config."""
    wl = WorkloadConfig(
        requests_per_second=1000.0,
        read_ratio=0.75,
        duration_seconds=120.0,
        pattern=WorkloadPattern.BURST,
        burst_multiplier=3.0,
        seed=100,
    )
    assert wl.requests_per_second == 1000.0
    assert wl.read_ratio == 0.75
    assert wl.duration_seconds == 120.0
    assert wl.pattern == WorkloadPattern.BURST


def test_invalid_workload_read_ratio():
    """Read ratio must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        WorkloadConfig(requests_per_second=500.0, read_ratio=1.5)


def test_invalid_workload_rps():
    """RPS must be strictly positive."""
    with pytest.raises(ValidationError):
        WorkloadConfig(requests_per_second=0.0)


def test_failure_scenario_validation():
    """Test failure scenario definition."""
    scenario = FailureScenario(
        name="DB Slowdown Spike",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="db-1",
        degradation_factor=3.0,
    )
    assert scenario.failure_type == FailureType.DB_SLOWDOWN
    assert scenario.degradation_factor == 3.0
    assert scenario.recovery_mode == "instant_recovery"


def test_sample_architecture_json_file():
    """Verify backend/examples/sample_architecture.json parses and validates cleanly."""
    json_path = Path(__file__).resolve().parent.parent / "examples" / "sample_architecture.json"
    assert json_path.exists(), f"Sample architecture JSON file not found at {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate sub-structures
    graph = ArchitectureGraph(**data["architecture"])
    workload = WorkloadConfig(**data["workload"])
    constraints = Constraints(**data["constraints"])

    assert len(graph.components) == 4
    assert len(graph.connections) == 4
    assert workload.requests_per_second == 600.0
    assert constraints.max_p95_latency_ms == 150.0

    # Also validate as OptimizationRequest
    opt_req = OptimizationRequest(
        architecture=graph,
        workload=workload,
        constraints=constraints,
        objective=OptimizationObjective.BALANCED,
    )
    assert opt_req.max_candidates == 8
