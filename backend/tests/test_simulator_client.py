"""
Tests for Member 2 Simulator Client and Adapter
Covers:
- Case 8: Baseline simulation succeeds.
- Case 9: Simulator timeout or unavailable service.
- Case 10: Invalid simulator response.
- Case 16: Mock metrics are labelled as mock.
"""

import pytest
import httpx

from backend.integrations.simulator_client import (
    SimulatorClient,
    SimulatorClientError,
    SimulatorTimeoutError,
    SimulatorUnavailableError,
)
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    Component,
    ComponentType,
    Connection,
    Constraints,
    SimulationStatus,
    Workload,
)


def sample_architecture() -> Architecture:
    return Architecture(
        architecture_id="arch-sim-test-001",
        components=[
            Component(id="api-1", type=ComponentType.API_SERVER),
            Component(id="db-1", type=ComponentType.DATABASE, attributes={"cpu_cores": 2}),
        ],
        connections=[
            Connection(source="api-1", target="db-1")
        ],
        workload=Workload(requests_per_second=1000.0, read_ratio=0.8, write_ratio=0.2),
        constraints=Constraints(max_p95_latency_ms=200.0),
    )


@pytest.mark.asyncio
async def test_case_8_baseline_simulation_succeeds():
    """Case 8: Baseline simulation succeeds and returns validated metrics."""
    client = SimulatorClient(use_mock=True)
    req = BaselineSimulationRequest(
        run_id="run-baseline-001",
        architecture=sample_architecture(),
    )

    response = await client.run_baseline(req)
    assert response.run_id == "run-baseline-001"
    assert response.status == SimulationStatus.COMPLETED
    assert "p95_latency_ms" in response.metrics
    assert response.metrics["p95_latency_ms"] is not None
    assert response.metrics["p95_latency_ms"] > 0
    assert len(response.component_metrics) == 2


@pytest.mark.asyncio
async def test_case_16_mock_metrics_are_labelled_as_mock():
    """Case 16: Mock metrics are explicitly labelled as mock and never disguised."""
    client = SimulatorClient(use_mock=True)
    req = BaselineSimulationRequest(
        run_id="run-mock-check-001",
        architecture=sample_architecture(),
    )

    response = await client.run_baseline(req)
    assert response.is_mock is True
    assert response.source == "mock_simulator"
    assert "mock" in response.simulator_version.lower()


@pytest.mark.asyncio
async def test_case_9_simulator_timeout_or_unavailable(monkeypatch):
    """Case 9: Simulator timeout or unavailable service produces explicit structured error."""
    client = SimulatorClient(base_url="http://127.0.0.1:9999", use_mock=False)
    req = BaselineSimulationRequest(
        run_id="run-timeout-001",
        architecture=sample_architecture(),
    )

    # Simulate connection error
    async def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused to simulator")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with pytest.raises(SimulatorUnavailableError) as exc:
        await client.run_baseline(req)

    assert exc.value.code == "ERR_SIMULATOR_UNAVAILABLE"


@pytest.mark.asyncio
async def test_case_10_invalid_simulator_response(monkeypatch):
    """Case 10: Invalid simulator response (bad schema / missing fields) is caught and rejected."""
    client = SimulatorClient(base_url="http://127.0.0.1:9999", use_mock=False)
    req = BaselineSimulationRequest(
        run_id="run-bad-resp-001",
        architecture=sample_architecture(),
    )

    class MockResponse:
        status_code = 200
        def json(self):
            # Missing run_id and status required fields
            return {"bad_payload": True}

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with pytest.raises(SimulatorClientError) as exc:
        await client.run_baseline(req)

    assert "validation failed" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_case_25_real_simulator_contract_compatibility(monkeypatch):
    """Case 25: Real simulator contract compatibility - dispatches valid JSON and parses real response."""
    client = SimulatorClient(base_url="http://member2-sim:8001", use_mock=False)
    arch = sample_architecture()
    req = BaselineSimulationRequest(run_id="run-real-compat-001", architecture=arch)

    class MockRealSimulatorResponse:
        status_code = 200
        def json(self):
            return {
                "run_id": "run-real-compat-001",
                "status": "completed",
                "source": "member2_simulator",
                "is_mock": False,
                "metrics": {
                    "p95_latency_ms": 142.5,
                    "throughput_rps": 1000.0,
                    "cost_per_hour": 1.20,
                    "availability": 0.9995,
                },
                "component_metrics": [],
                "warnings": [],
                "assumptions": ["Real engine load calculation"],
                "simulator_version": "member2-engine-v1.0.0",
            }

    async def mock_post(self, url, json=None, **kwargs):
        assert "/api/v1/simulate/baseline" in url
        # Ensure enums were properly serialized as strings in JSON payload
        assert isinstance(json["architecture"]["components"][0]["type"], str)
        return MockRealSimulatorResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = await client.run_baseline(req)
    assert response.is_mock is False
    assert response.source == "member2_simulator"
    assert response.metrics["p95_latency_ms"] == 142.5
    assert response.simulator_version == "member2-engine-v1.0.0"


def test_metric_diff_zero_division_safety():
    """Verify mock diagnostic safely handles edge cases without zero-division crashes."""
    from backend.shared.schemas import DiagnosticExperimentRequest, SupportedDiagnosticExperiment
    client = SimulatorClient(use_mock=True)

    baseline_zero = BaselineSimulationResponse(
        run_id="run-zero-base",
        status=SimulationStatus.COMPLETED,
        source="mock_simulator",
        is_mock=True,
        metrics={
            "p95_latency_ms": 0.0,
            "throughput_rps": 0.0,
            "cost_per_hour": 0.0,
            "availability": 0.0,
        },
        component_metrics=[],
    )

    req = DiagnosticExperimentRequest(
        experiment_id="exp-zero-01",
        baseline_run_id="run-zero-base",
        experiment_type=SupportedDiagnosticExperiment.INCREASE_WORKLOAD,
        target_components=["api-1"],
        parameters_to_change={"multiplier": 2.0},
        reason="Zero baseline safety check",
        hypotheses_tested=["HYP-001"],
        expected_evidence="No exception thrown",
    )

    # Should calculate without ZeroDivisionError
    res = client._run_mock_diagnostic(req, baseline_zero)
    assert res.status == SimulationStatus.COMPLETED
