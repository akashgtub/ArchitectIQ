"""
Tests for Member 2 Optimization Handoff Builder
Covers:
- Case 17: Handoff conforms to the shared schema.
- Case 18: Handoff contains no invented metric values.
- Case 19: Original workload and hard constraints remain unchanged.
"""

import pytest

from backend.ai_agent.handoff_builder import HandoffBuilder
from backend.ai_agent.root_cause import RootCauseInvestigator
from backend.integrations.simulator_client import SimulatorClient
from backend.shared.schemas import (
    Architecture,
    ArchitectureValidationResult,
    BaselineSimulationRequest,
    Component,
    ComponentType,
    Connection,
    Constraints,
    Member1Handoff,
    SCHEMA_VERSION,
    Workload,
)


def sample_architecture_with_constraints() -> Architecture:
    return Architecture(
        architecture_id="arch-handoff-001",
        components=[
            Component(id="api-1", type=ComponentType.API_SERVER),
            Component(id="db-1", type=ComponentType.DATABASE, attributes={"cpu_cores": 2}),
        ],
        connections=[
            Connection(source="api-1", target="db-1")
        ],
        workload=Workload(
            requests_per_second=1500.0,
            read_ratio=0.85,
            write_ratio=0.15,
            concurrent_users=400,
        ),
        constraints=Constraints(
            max_p95_latency_ms=180.0,
            min_throughput_rps=1200.0,
            max_cost_per_hour=1.50,
            min_availability=0.999,
        ),
    )


@pytest.mark.asyncio
async def test_case_17_handoff_conforms_to_shared_schema():
    """Case 17: Handoff passes full Pydantic validation against Member1Handoff schema."""
    sim_client = SimulatorClient(use_mock=True)
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=2)
    arch = sample_architecture_with_constraints()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-h-001", architecture=arch)
    )
    rc_result = await investigator.investigate(arch, baseline, investigation_id="inv-h-001")

    builder = HandoffBuilder()
    val_result = ArchitectureValidationResult(valid=True, issues=[], assumptions=["Test assumption"])

    handoff = builder.build_handoff(
        investigation_id="inv-h-001",
        architecture=arch,
        validation_result=val_result,
        baseline=baseline,
        root_cause_result=rc_result,
        model_id="gemini-2.0-flash",
    )

    # Must be valid Member1Handoff instance
    assert isinstance(handoff, Member1Handoff)
    assert handoff.schema_version == SCHEMA_VERSION
    assert handoff.investigation_id == "inv-h-001"
    assert handoff.provenance.model_id == "gemini-2.0-flash"
    assert handoff.provenance.schema_version == SCHEMA_VERSION

    # Can be serialized to JSON and deserialized back cleanly
    json_str = handoff.model_dump_json()
    reparsed = Member1Handoff.model_validate_json(json_str)
    assert reparsed.investigation_id == handoff.investigation_id


@pytest.mark.asyncio
async def test_case_18_handoff_contains_no_invented_metrics():
    """Case 18: Handoff baseline metrics match simulator output exactly without fabrication."""
    sim_client = SimulatorClient(use_mock=True)
    arch = sample_architecture_with_constraints()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-h-002", architecture=arch)
    )

    # If simulator didn't return a metric, it must be absent or None, never fabricated
    assert "p95_latency_ms" in baseline.metrics
    sim_p95 = baseline.metrics["p95_latency_ms"]

    builder = HandoffBuilder()
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=1)
    rc_result = await investigator.investigate(arch, baseline, investigation_id="inv-h-002")
    val_result = ArchitectureValidationResult(valid=True, issues=[], assumptions=[])

    handoff = builder.build_handoff(
        investigation_id="inv-h-002",
        architecture=arch,
        validation_result=val_result,
        baseline=baseline,
        root_cause_result=rc_result,
    )

    # The handoff baseline metric MUST match the simulator baseline metric
    assert handoff.baseline.metrics.get("p95_latency_ms") == sim_p95


@pytest.mark.asyncio
async def test_case_19_workload_and_hard_constraints_remain_unchanged():
    """Case 19: Original workload and hard constraints are preserved exactly in handoff."""
    sim_client = SimulatorClient(use_mock=True)
    arch = sample_architecture_with_constraints()

    baseline = await sim_client.run_baseline(
        BaselineSimulationRequest(run_id="run-h-003", architecture=arch)
    )
    investigator = RootCauseInvestigator(simulator_client=sim_client, max_experiments=1)
    rc_result = await investigator.investigate(arch, baseline, investigation_id="inv-h-003")
    val_result = ArchitectureValidationResult(valid=True, issues=[], assumptions=[])

    builder = HandoffBuilder()
    handoff = builder.build_handoff(
        investigation_id="inv-h-003",
        architecture=arch,
        validation_result=val_result,
        baseline=baseline,
        root_cause_result=rc_result,
    )

    # Check preserved workload
    assert handoff.architecture.workload.requests_per_second == 1500.0
    assert handoff.architecture.workload.read_ratio == 0.85
    assert handoff.architecture.workload.write_ratio == 0.15
    assert handoff.architecture.workload.concurrent_users == 400

    # Check preserved hard constraints
    hc = handoff.optimization_handoff.hard_constraints
    assert hc["max_p95_latency_ms"] == 180.0
    assert hc["min_throughput_rps"] == 1200.0
    assert hc["max_cost_per_hour"] == 1.50
    assert hc["min_availability"] == 0.999
