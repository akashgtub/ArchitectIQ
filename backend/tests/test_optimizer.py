"""Unit and integration tests for the architecture optimization engine."""

import copy
import json
from pathlib import Path
import pytest

from backend.optimizer.optimizer import ArchitectureOptimizer, optimize_architecture
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Connection,
    Constraints,
    OptimizationObjective,
    PathType,
    WorkloadConfig,
)


@pytest.fixture
def baseline_graph() -> ArchitectureGraph:
    """Fixture providing a standard 3-tier architecture with load balancer, API servers, cache, and DB."""
    lb = Component(id="lb-1", type=ComponentType.LOAD_BALANCER, capacity_rps=2000.0, replicas=1, cost_per_month_usd=25.0)
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=400.0, replicas=2, base_latency_ms=10.0, cost_per_month_usd=40.0)
    cache = Component(id="cache-1", type=ComponentType.CACHE, capacity_rps=2500.0, replicas=1, base_latency_ms=2.0, cache_hit_ratio=0.8, cost_per_month_usd=60.0)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=600.0, replicas=1, base_latency_ms=25.0, cost_per_month_usd=150.0)

    conns = [
        Connection(source="lb-1", target="api-1", path_type=PathType.BOTH),
        Connection(source="api-1", target="cache-1", path_type=PathType.READ),
        Connection(source="api-1", target="db-1", path_type=PathType.WRITE),
        Connection(source="cache-1", target="db-1", path_type=PathType.READ),
    ]
    return ArchitectureGraph(components=[lb, api, cache, db], connections=conns)


@pytest.fixture
def test_workload() -> WorkloadConfig:
    """Fixture providing a moderate workload."""
    return WorkloadConfig(
        requests_per_second=600.0,
        read_ratio=0.8,
        duration_seconds=10.0,
        seed=42,
    )


def test_candidate_generation_and_schema_validity(baseline_graph, test_workload):
    """Generated candidates must be valid ArchitectureGraph instances and respect max_candidates."""
    opt = ArchitectureOptimizer(
        architecture=baseline_graph,
        workload=test_workload,
        max_candidates=5,
    )
    candidates = opt._generate_candidate_graphs()

    assert len(candidates) <= 5
    assert len(candidates) > 0
    for cand_id, mods, graph in candidates:
        assert isinstance(cand_id, str)
        assert len(mods) > 0
        assert isinstance(graph, ArchitectureGraph)
        assert len(graph.components) >= len(baseline_graph.components)


def test_original_architecture_is_not_mutated(baseline_graph, test_workload):
    """Running optimization must not mutate the original baseline architecture object."""
    original_api_replicas = baseline_graph.get_component("api-1").replicas
    original_db_capacity = baseline_graph.get_component("db-1").capacity_rps
    original_components_count = len(baseline_graph.components)

    opt_result = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MINIMIZE_LATENCY,
    )

    assert baseline_graph.get_component("api-1").replicas == original_api_replicas
    assert baseline_graph.get_component("db-1").capacity_rps == original_db_capacity
    assert len(baseline_graph.components) == original_components_count
    assert opt_result.status == "success"


def test_latency_oriented_ranking(baseline_graph, test_workload):
    """MINIMIZE_LATENCY objective must sort feasible candidates by p95 latency ascending."""
    opt_result = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MINIMIZE_LATENCY,
        max_candidates=6,
    )

    feasible = [c for c in opt_result.ranked_candidates if c.is_feasible]
    assert len(feasible) > 0
    # Recommended candidate must be the lowest p95 latency candidate among feasible
    min_lat = min(c.metrics.p95_latency_ms for c in feasible)
    assert opt_result.recommended_candidate.metrics.p95_latency_ms == min_lat

    # Check ascending order of p95 latency
    for i in range(len(feasible) - 1):
        assert feasible[i].metrics.p95_latency_ms <= feasible[i + 1].metrics.p95_latency_ms


def test_cost_oriented_ranking(baseline_graph, test_workload):
    """MINIMIZE_COST objective must sort feasible candidates by cost ascending."""
    opt_result = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MINIMIZE_COST,
        max_candidates=6,
    )

    feasible = [c for c in opt_result.ranked_candidates if c.is_feasible]
    assert len(feasible) > 0
    min_cost = min(c.metrics.total_monthly_cost_usd for c in feasible)
    assert opt_result.recommended_candidate.metrics.total_monthly_cost_usd == min_cost

    for i in range(len(feasible) - 1):
        assert feasible[i].metrics.total_monthly_cost_usd <= feasible[i + 1].metrics.total_monthly_cost_usd


def test_throughput_oriented_ranking(baseline_graph, test_workload):
    """MAXIMIZE_THROUGHPUT objective must prioritize completed throughput."""
    opt_result = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MAXIMIZE_THROUGHPUT,
        max_candidates=6,
    )

    feasible = [c for c in opt_result.ranked_candidates if c.is_feasible]
    assert len(feasible) > 0
    max_tp = max(c.metrics.throughput_rps for c in feasible)
    assert opt_result.recommended_candidate.metrics.throughput_rps == pytest.approx(max_tp, abs=0.1)


def test_hard_constraints_priority_over_cheaper_infeasible():
    """Cheaper candidate violating hard latency constraint must be rejected in favor of more expensive feasible candidate."""
    # Build overloaded baseline: 1 API replica (capacity 300) under 450 RPS load => high p95 latency
    api = Component(id="api-1", type=ComponentType.API_SERVER, capacity_rps=300.0, replicas=1, base_latency_ms=10.0, cost_per_month_usd=40.0)
    db = Component(id="db-1", type=ComponentType.DATABASE, capacity_rps=800.0, replicas=1, base_latency_ms=20.0, cost_per_month_usd=120.0)
    graph = ArchitectureGraph(components=[api, db], connections=[Connection(source="api-1", target="db-1")])

    workload = WorkloadConfig(requests_per_second=450.0, duration_seconds=10.0, seed=42)

    # Hard constraint: max p95 latency = 50ms, budget = $300/mo
    # Baseline with 1 replica has high queue wait (>50ms) -> infeasible
    # Scaled candidate with 2 or 3 replicas costs more ($40/mo per extra replica) but passes latency constraint
    constraints = Constraints(max_p95_latency_ms=60.0, monthly_budget_usd=300.0)

    opt_result = optimize_architecture(
        architecture=graph,
        workload=workload,
        constraints=constraints,
        objective=OptimizationObjective.MINIMIZE_COST,
        max_candidates=4,
    )

    assert opt_result.status == "success"
    rec = opt_result.recommended_candidate
    assert rec is not None
    assert rec.is_feasible is True
    assert rec.metrics.p95_latency_ms <= 60.0
    # Must have added replica to handle the 450 RPS load
    api_comp = rec.architecture.get_component("api-1")
    assert api_comp.replicas > 1


def test_no_feasible_candidate_when_budget_impossible(baseline_graph, test_workload):
    """When budget is set below minimum feasible cost, return no_feasible_candidate."""
    # Baseline costs $315/mo. Set hard budget to $100/mo.
    impossible_constraints = Constraints(monthly_budget_usd=100.0)

    opt_result = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        constraints=impossible_constraints,
        objective=OptimizationObjective.MINIMIZE_COST,
    )

    assert opt_result.status == "no_feasible_candidate"
    assert opt_result.recommended_candidate is None
    assert opt_result.feasible_candidates_count == 0
    assert "No candidate architecture satisfied all hard constraints" in opt_result.trade_off_analysis


def test_deterministic_optimization_ranking(baseline_graph, test_workload):
    """Repeated optimization runs with identical input must produce identical rankings and scores."""
    res1 = optimize_architecture(baseline_graph, test_workload, objective=OptimizationObjective.BALANCED)
    res2 = optimize_architecture(baseline_graph, test_workload, objective=OptimizationObjective.BALANCED)

    assert res1.recommended_candidate.candidate_id == res2.recommended_candidate.candidate_id
    assert res1.recommended_candidate.objective_score == res2.recommended_candidate.objective_score
    assert len(res1.ranked_candidates) == len(res2.ranked_candidates)
    for c1, c2 in zip(res1.ranked_candidates, res2.ranked_candidates):
        assert c1.candidate_id == c2.candidate_id
        assert c1.objective_score == c2.objective_score
        assert c1.rank == c2.rank


def test_optimization_request_json_file():
    """Verify backend/examples/optimization_request.json runs and optimizes successfully."""
    path = Path(__file__).resolve().parent.parent / "examples" / "optimization_request.json"
    assert path.exists()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    graph = ArchitectureGraph(**data["architecture"])
    wl = WorkloadConfig(**data["workload"])
    wl.duration_seconds = 10.0  # Fast test duration
    constraints = Constraints(**data["constraints"])
    objective = OptimizationObjective(data["objective"])

    res = optimize_architecture(graph, wl, constraints, objective, max_candidates=data["max_candidates"])
    assert res.status == "success"
    assert res.recommended_candidate is not None
    assert len(res.trade_off_analysis) > 0
