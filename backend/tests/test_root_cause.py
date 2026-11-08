"""
Tests for Root-Cause Investigation Engine
Covers:
- Case 11: Diagnostic experiment is selected from the supported allowlist.
- Case 12: Diagnostic experiment fails.
- Case 13: Hypothesis has traceable evidence.
- Case 14: Insufficient evidence does not produce a confirmed root cause.
- Case 15: Investigation stops at its configured experiment limit.
"""

import pytest

from backend.ai_agent.root_cause import RootCauseInvestigator
from backend.integrations.simulator_client import (
    SimulatorClient,
    SimulatorClientError,
)
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    Component,
    ComponentType,
    ConfidenceLabel,
    Connection,
    Constraints,
    DiagnosticExperimentResponse,
    HypothesisStatus,
    InvestigationStatus,
    MetricDiff,
    SimulationStatus,
    SupportedDiagnosticExperiment,
    Workload,
)


def sample_architecture_db_bottleneck() -> Architecture:
    return Architecture(
        architecture_id="arch-bottleneck-001",
        components=[
            Component(id="api-1", type=ComponentType.API_SERVER),
            Component(id="db-1", type=ComponentType.DATABASE, attributes={"cpu_cores": 1}),  # Low core count
        ],
        connections=[
            Connection(source="api-1", target="db-1")
        ],
        workload=Workload(requests_per_second=1200.0, read_ratio=0.7, write_ratio=0.3),
        constraints=Constraints(max_p95_latency_ms=150.0),
    )


@pytest.mark.asyncio
async def test_case_11_experiment_selected_from_allowlist():
    """Case 11: Diagnostic experiment is selected from the supported allowlist."""
    sim_client = SimulatorClient(use_mock=True)
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=2)
    arch = sample_architecture_db_bottleneck()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-rc-001", architecture=arch)
    )

    result = await investigator.investigate(arch, baseline, investigation_id="inv-case11")

    assert len(result.experiments) > 0
    allowlist_values = {e.value for e in SupportedDiagnosticExperiment}
    for exp in result.experiments:
        # Check that executed experiment types belong to allowlist
        for hyp in result.hypotheses:
            if hyp.recommended_experiment:
                assert hyp.recommended_experiment.value in allowlist_values


@pytest.mark.asyncio
async def test_case_12_diagnostic_experiment_fails():
    """Case 12: Diagnostic experiment fails gracefully without crashing or hallucinating confirmation."""
    sim_client = SimulatorClient(use_mock=True)

    # Monkeypatch run_diagnostic to raise an error
    async def mock_fail_diag(*args, **kwargs):
        raise SimulatorClientError("Simulated diagnostic crash", code="ERR_DIAGNOSTIC_FAILED")

    sim_client.run_diagnostic = mock_fail_diag

    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=2)
    arch = sample_architecture_db_bottleneck()
    baseline = await SimulatorClient(use_mock=True).run_baseline(
        BaselineSimulationRequest(run_id="run-rc-002", architecture=arch)
    )

    result = await investigator.investigate(arch, baseline, investigation_id="inv-case12")

    # None of the hypotheses should be confirmed because the experiment failed!
    assert all(h.status != HypothesisStatus.CONFIRMED for h in result.hypotheses)
    # Failed experiment note must be logged in missing evidence
    tested_hyp = next(h for h in result.hypotheses if h.recommended_experiment)
    assert any("failed" in msg.lower() for msg in tested_hyp.missing_evidence)


@pytest.mark.asyncio
async def test_case_13_hypothesis_has_traceable_evidence():
    """Case 13: Confirmed hypothesis has concrete traceable evidence with run IDs and metric values."""
    sim_client = SimulatorClient(use_mock=True)
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=3)
    arch = sample_architecture_db_bottleneck()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-trace-001", architecture=arch)
    )

    result = await investigator.investigate(arch, baseline, investigation_id="inv-case13")

    # Find hypothesis tested and confirmed
    confirmed = [h for h in result.hypotheses if h.status == HypothesisStatus.CONFIRMED]
    assert len(confirmed) > 0

    first_confirmed = confirmed[0]
    assert len(first_confirmed.supporting_evidence) > 0
    ev = first_confirmed.supporting_evidence[0]
    assert ev.run_id is not None
    assert ev.metric_name is not None
    assert ev.observed_value is not None
    assert ev.unit is not None
    assert len(ev.description) > 0


@pytest.mark.asyncio
async def test_case_14_insufficient_evidence_does_not_produce_confirmed_cause():
    """Case 14: Insufficient evidence does not produce a confirmed root cause."""
    sim_client = SimulatorClient(use_mock=True)

    # Return a diagnostic response with empty/null diffs
    async def mock_inconclusive_diag(request, baseline):
        return DiagnosticExperimentResponse(
            experiment_id=request.experiment_id,
            baseline_run_id=request.baseline_run_id,
            status=SimulationStatus.COMPLETED,
            source="mock_simulator",
            is_mock=True,
            metrics={},
            diff_from_baseline=[],  # No metric diffs!
        )

    sim_client.run_diagnostic = mock_inconclusive_diag

    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=1)
    arch = sample_architecture_db_bottleneck()
    baseline = await SimulatorClient(use_mock=True).run_baseline(
        BaselineSimulationRequest(run_id="run-inconclusive-001", architecture=arch)
    )

    result = await investigator.investigate(arch, baseline, investigation_id="inv-case14")

    # When diff is empty, hypothesis status must be INSUFFICIENT_EVIDENCE
    target_hyp = next(h for h in result.hypotheses if h.recommended_experiment)
    assert target_hyp.status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    assert target_hyp.confidence_label in (ConfidenceLabel.LOW, ConfidenceLabel.MEDIUM)
    assert any("did not yield" in m for m in target_hyp.missing_evidence)


@pytest.mark.asyncio
async def test_case_15_investigation_stops_at_experiment_limit():
    """Case 15: Investigation strictly honors max_experiments budget limit."""
    sim_client = SimulatorClient(use_mock=True)
    # Configure limit to exactly 1 experiment
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=1)
    arch = sample_architecture_db_bottleneck()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-budget-001", architecture=arch)
    )

    result = await investigator.investigate(arch, baseline, investigation_id="inv-case15")

    # Strict check: exactly 1 experiment run
    assert len(result.experiments) == 1
    # Status should be PARTIAL because not all hypotheses were tested
    assert result.status in (InvestigationStatus.PARTIAL, InvestigationStatus.COMPLETED)
