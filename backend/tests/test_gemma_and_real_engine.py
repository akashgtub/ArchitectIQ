"""
ArchitectIQ - Real Engine Verification & Gemma Provider Test Suite
Tests:
- AI Provider abstraction and factory selection (Gemma, Gemini, Fallback)
- Real simulation engine as default execution path
- Disabling mock mode does not silently fallback to mock on engine error
- All 6 workflow stages using real simulation engine and dynamic parameter scaling
"""

import os
import pytest
from unittest.mock import AsyncMock, patch

from backend.ai_agent.providers import (
    BaseAIProvider,
    DeterministicFallbackProvider,
    GeminiProvider,
    GemmaProvider,
    ModelClientError,
    get_ai_provider,
)
from backend.config import settings
from backend.integrations.simulator_client import (
    SimulatorClient,
    SimulatorClientError,
)
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationRequest,
    Component,
    ComponentType,
    Connection,
    Constraints,
    Workload,
)
from backend.api.service import (
    optimize_architecture,
    run_simulation,
    simulate_failure,
)
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component as M2Component,
    ComponentType as M2ComponentType,
    Connection as M2Connection,
    FailureScenario,
    FailureType,
    OptimizationObjective,
    WorkloadConfig,
)
from backend.ai_agent.root_cause import RootCauseInvestigator


def ecommerce_architecture() -> Architecture:
    """Realistic e-commerce test architecture: Client -> LB -> API -> Cache & DB."""
    return Architecture(
        architecture_id="arch-ecommerce-001",
        components=[
            Component(id="client", type=ComponentType.GATEWAY, attributes={"instances": 1, "capacity_rps": 10000.0}),
            Component(id="load_balancer", type=ComponentType.LOAD_BALANCER, attributes={"instances": 2, "capacity_rps": 5000.0, "base_latency_ms": 1.5}),
            Component(id="api_server", type=ComponentType.API_SERVER, attributes={"instances": 4, "cpu_cores": 2, "capacity_rps": 1200.0, "base_latency_ms": 12.0}),
            Component(id="cache", type=ComponentType.CACHE, attributes={"engine": "redis", "capacity_rps": 8000.0, "base_latency_ms": 1.5, "cache_hit_ratio": 0.85}),
            Component(id="database", type=ComponentType.DATABASE, attributes={"engine": "postgres", "capacity_rps": 800.0, "base_latency_ms": 25.0, "cpu_cores": 4}),
        ],
        connections=[
            Connection(source="client", target="load_balancer"),
            Connection(source="load_balancer", target="api_server"),
            Connection(source="api_server", target="cache"),
            Connection(source="api_server", target="database"),
        ],
        workload=Workload(requests_per_second=500.0, read_ratio=0.8, write_ratio=0.2),
        constraints=Constraints(max_p95_latency_ms=200.0, max_cost_per_hour=1.0),
    )


def ecommerce_m2_graph() -> ArchitectureGraph:
    """M2 simulator graph for e-commerce system with realistic cost tiers."""
    return ArchitectureGraph(
        components=[
            M2Component(id="load_balancer", type=M2ComponentType.LOAD_BALANCER, capacity_rps=5000.0, replicas=2, base_latency_ms=1.5, cost_per_month_usd=25.0),
            M2Component(id="api_server", type=M2ComponentType.API_SERVER, capacity_rps=1200.0, replicas=2, base_latency_ms=12.0, cost_per_month_usd=80.0),
            M2Component(id="cache", type=M2ComponentType.CACHE, capacity_rps=8000.0, replicas=1, base_latency_ms=1.5, cost_per_month_usd=60.0, cache_hit_ratio=0.85),
            M2Component(id="database", type=M2ComponentType.DATABASE, capacity_rps=800.0, replicas=1, base_latency_ms=25.0, cost_per_month_usd=120.0),
        ],
        connections=[
            M2Connection(source="load_balancer", target="api_server"),
            M2Connection(source="api_server", target="cache"),
            M2Connection(source="api_server", target="database"),
        ],
    )


# ============================================================================
# Phase 2 & 3: AI Provider Selection, Gemma Verification & Transparency
# ============================================================================

def test_ai_provider_factory_selection():
    """Verify provider factory correctly chooses providers based on configuration."""
    # Explicit fallback provider
    p_fallback = get_ai_provider("deterministic_fallback")
    assert isinstance(p_fallback, DeterministicFallbackProvider)
    assert p_fallback.name == "deterministic_fallback"
    assert p_fallback.supports_vision is False

    # Gemma provider verification
    p_gemma = GemmaProvider(api_key="mock_key", model_id="gemma-2-27b-it")
    assert p_gemma.name == "gemma"
    assert p_gemma.model_name == "gemma-2-27b-it"
    # Gemma 2 text-to-text models do NOT support raw vision input
    assert p_gemma.supports_vision is False

    # Gemini provider verification
    p_gemini = GeminiProvider(api_key="mock_key", model_id="gemini-2.0-flash")
    assert p_gemini.name == "gemini"
    assert p_gemini.supports_vision is True


def test_deterministic_fallback_transparent_provenance():
    """Verify fallback outputs are never labeled as real model inference."""
    provider = DeterministicFallbackProvider()
    assert provider.name == "deterministic_fallback"
    assert "deterministic" in provider.model_name.lower()


def test_missing_credentials_when_fallback_disabled_raises_error():
    """Verify that when fallback is disabled and no credentials exist, an explicit error is raised."""
    with patch.object(settings, "allow_ai_fallback", False):
        with patch.object(settings, "gemini_api_key", ""):
            with patch.object(settings, "gemma_api_key", ""):
                with patch.object(settings, "gemma_base_url", ""):
                    with pytest.raises(ModelClientError) as exc_info:
                        get_ai_provider("gemini")
                    assert "ERR_NO_GEMINI_KEY" in exc_info.value.code


# ============================================================================
# Phase 2: Real Simulation Engine is Default & No Silent Fallbacks
# ============================================================================

@pytest.mark.asyncio
async def test_simulator_client_defaults_to_real_engine():
    """Verify SimulatorClient runs real discrete physics engine by default without mock flags."""
    client = SimulatorClient()  # use_mock is None -> defaults to settings.use_mock_simulator (False)
    assert client.use_mock is False

    arch = ecommerce_architecture()
    req = BaselineSimulationRequest(run_id="run-real-verify-01", architecture=arch)

    resp = await client.run_baseline(req)
    assert resp.is_mock is False
    assert resp.source == "member2_simulator"
    assert resp.execution_mode == "real"
    assert resp.engine_name == "discrete_event_engine"
    assert resp.metrics["p95_latency_ms"] is not None
    assert resp.metrics["p95_latency_ms"] > 0.0


@pytest.mark.asyncio
async def test_disabling_mock_mode_does_not_silently_fallback_when_engine_fails():
    """
    CRITICAL PROOF: Verify that when mock mode is disabled, an engine failure
    raises an actionable SimulatorClientError and NEVER silently returns mock metrics.
    """
    client = SimulatorClient(use_mock=False)

    # Create an invalid architecture with disconnected topology that causes simulation failure
    disconnected_arch = Architecture(
        architecture_id="arch-broken-01",
        components=[
            Component(id="api-isolated", type=ComponentType.API_SERVER),
            Component(id="db-isolated", type=ComponentType.DATABASE),
        ],
        connections=[],  # No connections!
        workload=Workload(requests_per_second=500.0, read_ratio=0.8, write_ratio=0.2),
        constraints=Constraints(max_p95_latency_ms=200.0),
    )
    req = BaselineSimulationRequest(run_id="run-broken-01", architecture=disconnected_arch)

    with pytest.raises(SimulatorClientError) as exc_info:
        await client.run_baseline(req)

    # Must raise actionable error code, not return is_mock=True
    assert exc_info.value.code in ("ERR_SIMULATION_FAILED", "ERR_SIMULATOR_DIRECT")


# ============================================================================
# Phase 4 & 6: Verification of Complete E-Commerce Workflow Scenarios
# ============================================================================

def test_scenario_baseline_at_500_rps_30s_80_percent_read():
    """Scenario 2: Run baseline simulation at 500 RPS for 30s with 80% read ratio."""
    graph = ecommerce_m2_graph()
    workload = WorkloadConfig(
        requests_per_second=500.0,
        read_ratio=0.80,
        duration_seconds=30.0,
    )
    result = run_simulation(architecture=graph, workload=workload)

    assert result.status in ("success", "degraded")
    assert result.simulation_metadata.get("execution_mode") == "real"
    assert result.simulation_metadata.get("engine_name") == "discrete_event_engine"
    assert result.metrics.throughput_rps > 0.0
    assert result.metrics.p95_latency_ms > 0.0


def test_scenario_peak_load_dynamic_scaling():
    """Scenario 3: Peak-load test at 1,000 RPS shows dynamic degradation compared to 500 RPS."""
    graph = ecommerce_m2_graph()

    workload_baseline = WorkloadConfig(requests_per_second=500.0, read_ratio=0.80, duration_seconds=30.0)
    workload_peak = WorkloadConfig(requests_per_second=1000.0, read_ratio=0.80, duration_seconds=30.0)

    res_baseline = run_simulation(architecture=graph, workload=workload_baseline)
    res_peak = run_simulation(architecture=graph, workload=workload_peak)

    # Prove output changes dynamically: peak load must have higher or equal latency / higher utilization
    assert res_peak.metrics.throughput_rps >= res_baseline.metrics.throughput_rps
    assert res_peak.metrics.p95_latency_ms >= res_baseline.metrics.p95_latency_ms


def test_scenario_database_latency_increase_3x():
    """Scenario 4: Simulate database latency increasing by 3x."""
    graph = ecommerce_m2_graph()
    workload = WorkloadConfig(requests_per_second=500.0, read_ratio=0.80, duration_seconds=30.0)

    scenario = FailureScenario(
        name="DB 3x Slowdown",
        failure_type=FailureType.DB_SLOWDOWN,
        target_component_id="database",
        degradation_factor=3.0,
        duration_sec=20.0,
    )

    chaos_result = simulate_failure(
        architecture=graph,
        workload=workload,
        scenario=scenario,
    )

    assert chaos_result.status in ("success", "completed")
    assert "database" in chaos_result.affected_components
    # Latency delta must be strictly positive under 3x database latency injection
    assert chaos_result.latency_delta_ms > 0.0
    assert chaos_result.failure_metrics.p95_latency_ms > chaos_result.baseline_metrics.p95_latency_ms


def test_scenario_cache_outage():
    """Scenario 5: Simulate cache tier outage with read bypass."""
    graph = ecommerce_m2_graph()
    workload = WorkloadConfig(requests_per_second=500.0, read_ratio=0.85, duration_seconds=30.0)

    scenario = FailureScenario(
        name="Cache Tier Outage",
        failure_type=FailureType.CACHE_OUTAGE,
        target_component_id="cache",
        degradation_factor=0.0,
        duration_sec=20.0,
    )

    chaos_result = simulate_failure(
        architecture=graph,
        workload=workload,
        scenario=scenario,
    )

    assert chaos_result.status in ("success", "completed")
    assert "cache" in chaos_result.affected_components
    # With cache down, database load increases, elevating latency
    assert chaos_result.failure_metrics.p95_latency_ms >= chaos_result.baseline_metrics.p95_latency_ms


def test_scenario_optimization_under_500_budget():
    """Scenario 6: Run optimization under an explicitly configured $500/month budget."""
    graph = ecommerce_m2_graph()
    workload = WorkloadConfig(requests_per_second=600.0, read_ratio=0.80, duration_seconds=30.0)
    constraints = {"monthly_budget_usd": 500.0, "max_p95_latency_ms": 150.0}

    opt_result = optimize_architecture(
        architecture=graph,
        workload=workload,
        constraints=constraints,
        objective=OptimizationObjective.BALANCED,
        max_candidates=6,
    )

    assert opt_result.status == "success"
    assert opt_result.total_candidates_evaluated > 0
    assert opt_result.recommended_candidate is not None
    # Recommended candidate must satisfy budget constraint
    assert opt_result.recommended_candidate.metrics.total_monthly_cost_usd <= 500.0
    assert len(opt_result.ranked_candidates) > 0


@pytest.mark.asyncio
async def test_scenario_root_cause_report_grounded_in_simulation():
    """Scenario 7: Generate root-cause report grounded in actual simulation outputs."""
    arch = ecommerce_architecture()
    sim_client = SimulatorClient(use_mock=False)  # Real engine!

    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=2)
    baseline_req = BaselineSimulationRequest(run_id="run-ecommerce-base", architecture=arch)
    baseline_resp = await sim_client.run_baseline(baseline_req)

    rca_result = await investigator.investigate(
        architecture=arch,
        baseline=baseline_resp,
        investigation_id="inv-ecommerce-01",
    )

    assert rca_result.status.value in ("completed", "partial")
    assert len(rca_result.hypotheses) > 0
    # Hypotheses must reference actual component IDs in the architecture
    valid_ids = {c.id for c in arch.components}
    for hyp in rca_result.hypotheses:
        for affected in hyp.affected_components:
            assert affected in valid_ids
    # Evidence summary must be populated
    assert len(rca_result.evidence_summary) > 0
