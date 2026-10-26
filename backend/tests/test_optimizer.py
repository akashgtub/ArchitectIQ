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


def test_controlled_tradeoff_ranking_all_objectives(baseline_graph, test_workload):
    """Controlled test candidates with deliberately different metrics must rank correctly for each objective,
    and infeasible candidates must NEVER outrank feasible candidates."""
    from backend.simulator.schemas import PerformanceMetrics

    cand_cheap = {
        "candidate_id": "cand-cheap",
        "name": "Cost Minimized",
        "description": "Downscaled resources",
        "modifications": ["downscale"],
        "architecture": baseline_graph,
        "metrics": PerformanceMetrics(
            mean_latency_ms=70.0,
            p50_latency_ms=65.0,
            p95_latency_ms=85.0,
            p99_latency_ms=110.0,
            throughput_rps=250.0,
            error_rate=0.0,
            completed_requests=2500,
            dropped_requests=0,
            total_monthly_cost_usd=80.0,
            component_breakdown={},
        ),
        "is_feasible": True,
        "violations": [],
    }

    cand_fast = {
        "candidate_id": "cand-fast",
        "name": "Lowest Latency",
        "description": "Upgraded cache and provisioned SSD",
        "modifications": ["upgrade-db"],
        "architecture": baseline_graph,
        "metrics": PerformanceMetrics(
            mean_latency_ms=8.0,
            p50_latency_ms=7.0,
            p95_latency_ms=12.0,
            p99_latency_ms=18.0,
            throughput_rps=500.0,
            error_rate=0.0,
            completed_requests=5000,
            dropped_requests=0,
            total_monthly_cost_usd=450.0,
            component_breakdown={},
        ),
        "is_feasible": True,
        "violations": [],
    }

    cand_high_tp = {
        "candidate_id": "cand-high-tp",
        "name": "Max Throughput",
        "description": "Clustered replicas with high capacity",
        "modifications": ["cluster-scale"],
        "architecture": baseline_graph,
        "metrics": PerformanceMetrics(
            mean_latency_ms=22.0,
            p50_latency_ms=18.0,
            p95_latency_ms=30.0,
            p99_latency_ms=45.0,
            throughput_rps=1200.0,
            error_rate=0.0,
            completed_requests=12000,
            dropped_requests=0,
            total_monthly_cost_usd=380.0,
            component_breakdown={},
        ),
        "is_feasible": True,
        "violations": [],
    }

    cand_infeasible = {
        "candidate_id": "cand-infeasible",
        "name": "Super Cheap Infeasible",
        "description": "Extremely low cost but violates latency SLA",
        "modifications": ["extreme-downscale"],
        "architecture": baseline_graph,
        "metrics": PerformanceMetrics(
            mean_latency_ms=3.0,
            p50_latency_ms=2.0,
            p95_latency_ms=4.0,  # lower latency than all!
            p99_latency_ms=6.0,
            throughput_rps=2500.0,  # higher throughput than all!
            error_rate=0.0,
            completed_requests=25000,
            dropped_requests=0,
            total_monthly_cost_usd=25.0,  # cheaper than all!
            component_breakdown={},
        ),
        "is_feasible": False,
        "violations": ["p95 latency exceeds SLA"],
    }

    candidates = [cand_cheap, cand_fast, cand_high_tp, cand_infeasible]

    # 1. MINIMIZE_COST
    opt_cost = ArchitectureOptimizer(baseline_graph, test_workload, objective=OptimizationObjective.MINIMIZE_COST)
    ranked_cost = opt_cost._compute_objective_scores([dict(c) for c in candidates])
    assert ranked_cost[0]["candidate_id"] == "cand-cheap", "Cheapest feasible candidate must be ranked #1"
    assert ranked_cost[-1]["candidate_id"] == "cand-infeasible", "Infeasible candidate must never outrank feasible ones"
    assert ranked_cost[0]["rank"] == 1
    assert ranked_cost[0]["is_feasible"] is True

    # 2. MINIMIZE_LATENCY
    opt_lat = ArchitectureOptimizer(baseline_graph, test_workload, objective=OptimizationObjective.MINIMIZE_LATENCY)
    ranked_lat = opt_lat._compute_objective_scores([dict(c) for c in candidates])
    assert ranked_lat[0]["candidate_id"] == "cand-fast", "Lowest p95 latency feasible candidate must be ranked #1"
    assert ranked_lat[-1]["candidate_id"] == "cand-infeasible", "Infeasible candidate must never outrank feasible ones"

    # 3. MAXIMIZE_THROUGHPUT
    opt_tp = ArchitectureOptimizer(baseline_graph, test_workload, objective=OptimizationObjective.MAXIMIZE_THROUGHPUT)
    ranked_tp = opt_tp._compute_objective_scores([dict(c) for c in candidates])
    assert ranked_tp[0]["candidate_id"] == "cand-high-tp", "Highest throughput feasible candidate must be ranked #1"
    assert ranked_tp[-1]["candidate_id"] == "cand-infeasible", "Infeasible candidate must never outrank feasible ones"

    # 4. BALANCED
    opt_bal = ArchitectureOptimizer(baseline_graph, test_workload, objective=OptimizationObjective.BALANCED)
    ranked_bal = opt_bal._compute_objective_scores([dict(c) for c in candidates])
    assert ranked_bal[-1]["candidate_id"] == "cand-infeasible", "Infeasible candidate must be ranked last under balanced"
    for r in ranked_bal:
        assert "score" in r and r["score"] is not None


def test_changing_objective_changes_recommended_candidate(baseline_graph, test_workload):
    """Running optimization on the same baseline with different objectives must produce different recommendations
    when candidates present genuine trade-offs."""
    # Run under MINIMIZE_COST
    res_cost = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MINIMIZE_COST,
        max_candidates=6,
    )
    assert res_cost.status == "success"
    rec_cost = res_cost.recommended_candidate

    # Run under MINIMIZE_LATENCY
    res_lat = optimize_architecture(
        architecture=baseline_graph,
        workload=test_workload,
        objective=OptimizationObjective.MINIMIZE_LATENCY,
        max_candidates=6,
    )
    assert res_lat.status == "success"
    rec_lat = res_lat.recommended_candidate

    # Cost-minimizing recommendation must be cheaper than or equal to latency-minimizing recommendation
    assert rec_cost.metrics.total_monthly_cost_usd <= rec_lat.metrics.total_monthly_cost_usd

    # Latency-minimizing recommendation must achieve lower or equal p95 latency than cost-minimizing recommendation
    assert rec_lat.metrics.p95_latency_ms <= rec_cost.metrics.p95_latency_ms

    # The chosen candidates must be genuinely different
    assert rec_cost.candidate_id != rec_lat.candidate_id


def test_optimizer_strictly_preserves_baseline_and_workload(baseline_graph, test_workload):
    """The optimizer must preserve baseline architecture and workload inputs without mutating them."""
    import copy

    original_arch_dict = baseline_graph.model_dump()
    original_wl_dict = test_workload.model_dump()

    for obj in [
        OptimizationObjective.MINIMIZE_COST,
        OptimizationObjective.MINIMIZE_LATENCY,
        OptimizationObjective.MAXIMIZE_THROUGHPUT,
        OptimizationObjective.BALANCED,
    ]:
        res = optimize_architecture(
            architecture=baseline_graph,
            workload=test_workload,
            objective=obj,
            max_candidates=4,
        )
        assert res.status == "success"
        assert baseline_graph.model_dump() == original_arch_dict
        assert test_workload.model_dump() == original_wl_dict


def test_all_objectives_supported_via_api():
    """Verify that all 4 supported objectives are handled properly by the FastAPI endpoint."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    path = Path(__file__).resolve().parent.parent / "examples" / "sample_architecture.json"
    with open(path, "r", encoding="utf-8") as f:
        arch_data = json.load(f)

    workload_data = {
        "requests_per_second": 300.0,
        "read_ratio": 0.8,
        "duration_seconds": 5.0,
    }

    objectives = ["minimize_cost", "minimize_latency", "maximize_throughput", "balanced"]

    for obj in objectives:
        payload = {
            "architecture": arch_data["architecture"],
            "workload": workload_data,
            "objective": obj,
            "max_candidates": 4,
        }
        # Test both v1 and root route alias
        for endpoint in ["/api/v1/optimization/run", "/api/optimization/run"]:
            resp = client.post(endpoint, json=payload)
            assert resp.status_code == 200, f"Failed for {obj} on {endpoint}: {resp.text}"
            data = resp.json()
            assert data["objective"] == obj
            assert data["status"] in ["success", "no_feasible_candidate"]
            assert "ranked_candidates" in data
            assert len(data["ranked_candidates"]) > 0
            for cand in data["ranked_candidates"]:
                assert "candidate_id" in cand
                assert "metrics" in cand
                assert "is_feasible" in cand
                assert "objective_score" in cand
                assert "rank" in cand

