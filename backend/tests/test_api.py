"""
Unified Integration Tests for FastAPI API Routes
Covers:
- Member 1 routes:
  * /health & /api/v1/health
  * POST /api/v1/architecture/analyze
  * POST /api/v1/investigations
  * GET  /api/v1/investigations/{id}
  * GET  /api/v1/investigations/{id}/handoff
  * POST /api/v1/simulate/baseline
  * POST /api/v1/simulate/diagnostic
- Member 2 routes:
  * POST /api/simulation/run
  * POST /api/optimization/run
  * POST /api/chaos/run
  * Validation error cases (invalid graph, disconnected node, infeasible budget, invalid target)
  * JSON serialization safety
"""

import io
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.api.routes import router
from backend.main import app
from backend.shared.schemas import (
    ArchitectureAnalyzeResponse,
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    DiagnosticExperimentRequest,
    DiagnosticExperimentResponse,
    InvestigationDetailResponse,
    Member1Handoff,
    SupportedDiagnosticExperiment,
)

# Lightweight test client for Member 2 route tests
client = TestClient(app)


def create_dummy_png_bytes(width: int = 150, height: int = 150) -> bytes:
    img = Image.new("RGB", (width, height), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_payload() -> dict:
    """Load sample architecture fixture as a JSON dictionary."""
    path = Path(__file__).resolve().parent.parent / "examples" / "sample_architecture.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Use shorter duration for fast test execution
    data["workload"]["duration_seconds"] = 10.0
    return data


# ============================================================================
# Member 2 API Route Tests
# ============================================================================

def test_api_simulation_run_valid(sample_payload):
    """POST /api/simulation/run must execute simulation and return 200 with structured metrics."""
    resp = client.post("/api/simulation/run", json=sample_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in ("success", "degraded")
    assert data["simulation_type"] == "baseline"
    assert "metrics" in data
    assert data["metrics"]["throughput_rps"] > 0
    assert data["metrics"]["p50_latency_ms"] > 0
    assert data["metrics"]["total_monthly_cost_usd"] > 0
    assert isinstance(data["bottlenecks"], list)
    assert isinstance(data["assumptions"], list)


def test_api_simulation_run_invalid_graph():
    """POST /api/simulation/run with self-loop connection must return 422 Unprocessable Entity."""
    bad_payload = {
        "architecture": {
            "components": [
                {"id": "api-1", "type": "api_server", "capacity_rps": 500.0}
            ],
            "connections": [
                {"source": "api-1", "target": "api-1"}  # Self-loop
            ]
        },
        "workload": {
            "requests_per_second": 100.0,
            "duration_seconds": 5.0
        }
    }
    resp = client.post("/api/simulation/run", json=bad_payload)
    assert resp.status_code == 422
    assert "Self-loop connection detected" in resp.text


def test_api_simulation_run_disconnected_node():
    """POST /api/simulation/run with disconnected node must return 400 Bad Request."""
    disconnected_payload = {
        "architecture": {
            "components": [
                {"id": "lb-1", "type": "load_balancer", "capacity_rps": 1000.0},
                {"id": "api-1", "type": "api_server", "capacity_rps": 500.0},
                {"id": "orphan-node", "type": "database", "capacity_rps": 500.0}
            ],
            "connections": [
                {"source": "lb-1", "target": "api-1"}
            ]
        },
        "workload": {
            "requests_per_second": 100.0,
            "duration_seconds": 5.0
        }
    }
    resp = client.post("/api/simulation/run", json=disconnected_payload)
    assert resp.status_code == 400
    assert "Isolated / unreachable components detected" in resp.json()["detail"]


def test_api_optimization_run_valid(sample_payload):
    """POST /api/optimization/run must return ranked candidate architectures."""
    opt_payload = {
        "architecture": sample_payload["architecture"],
        "workload": sample_payload["workload"],
        "constraints": sample_payload["constraints"],
        "objective": "balanced",
        "max_candidates": 4,
    }
    resp = client.post("/api/optimization/run", json=opt_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in ("success", "no_feasible_candidate")
    assert data["objective"] == "balanced"
    assert data["total_candidates_evaluated"] > 0
    assert isinstance(data["ranked_candidates"], list)
    assert len(data["ranked_candidates"]) > 0
    assert len(data["trade_off_analysis"]) > 0


def test_api_optimization_infeasible_budget(sample_payload):
    """POST /api/optimization/run with impossible budget returns 200 with no_feasible_candidate status."""
    opt_payload = {
        "architecture": sample_payload["architecture"],
        "workload": sample_payload["workload"],
        "constraints": {"monthly_budget_usd": 10.0},  # Impossible $10 budget
        "objective": "minimize_cost",
        "max_candidates": 3,
    }
    resp = client.post("/api/optimization/run", json=opt_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "no_feasible_candidate"
    assert data["recommended_candidate"] is None
    assert data["feasible_candidates_count"] == 0


def test_api_chaos_run_valid(sample_payload):
    """POST /api/chaos/run must execute fault injection and return comparative metrics."""
    chaos_payload = {
        "architecture": sample_payload["architecture"],
        "workload": sample_payload["workload"],
        "scenario": {
            "name": "DB Latency Spike",
            "failure_type": "db_slowdown",
            "target_component_id": "db-1",
            "start_time_sec": 2.0,
            "duration_sec": 5.0,
            "degradation_factor": 3.0,
        }
    }
    resp = client.post("/api/chaos/run", json=chaos_payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "scenario" in data
    assert "baseline_metrics" in data
    assert "failure_metrics" in data
    assert "latency_delta_ms" in data
    assert "throughput_delta_rps" in data
    assert "resilience_summary" in data
    assert data["scenario"]["failure_type"] == "db_slowdown"


def test_api_chaos_run_invalid_target(sample_payload):
    """POST /api/chaos/run with invalid target component must return 400 Bad Request."""
    bad_chaos_payload = {
        "architecture": sample_payload["architecture"],
        "workload": sample_payload["workload"],
        "scenario": {
            "name": "Ghost DB Crash",
            "failure_type": "db_slowdown",
            "target_component_id": "non-existent-db-node",
            "degradation_factor": 2.0,
        }
    }
    resp = client.post("/api/chaos/run", json=bad_chaos_payload)
    assert resp.status_code == 400
    assert "not found in architecture" in resp.json()["detail"]


def test_api_json_serialization(sample_payload):
    """Ensure API responses strictly conform to valid JSON serialization without NaN or infinite values."""
    resp = client.post("/api/simulation/run", json=sample_payload)
    assert resp.status_code == 200
    json_text = json.dumps(resp.json())
    assert len(json_text) > 0
    assert "NaN" not in json_text
    assert "Infinity" not in json_text


# ============================================================================
# Member 1 API Route Tests
# ============================================================================

@pytest.mark.asyncio
async def test_case_20_api_responses_conform_to_schema():
    """Case 20: API response uses the agreed response schema across all endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        # 1. Health check
        health_resp = await async_client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # 2. Analyze architecture
        png_bytes = create_dummy_png_bytes()
        files = {"image": ("arch.png", png_bytes, "image/png")}
        data = {
            "requirements": "High performance payments gateway, target 200ms latency",
            "workload_json": '{"requests_per_second": 800, "read_ratio": 0.8, "write_ratio": 0.2}',
            "constraints_json": '{"max_p95_latency_ms": 200}',
        }

        analyze_resp = await async_client.post("/api/v1/architecture/analyze", data=data, files=files)
        assert analyze_resp.status_code == 200
        parsed_analyze = ArchitectureAnalyzeResponse(**analyze_resp.json())
        assert parsed_analyze.status == "validated"
        assert parsed_analyze.architecture is not None

        # 3. Start investigation
        arch_payload = parsed_analyze.architecture.model_dump()
        inv_resp = await async_client.post(
            "/api/v1/investigations",
            json={"architecture": arch_payload, "max_diagnostic_experiments": 2},
        )
        assert inv_resp.status_code == 201
        parsed_inv = InvestigationDetailResponse(**inv_resp.json())
        inv_id = parsed_inv.investigation_id
        assert parsed_inv.handoff_ready is True
        assert parsed_inv.baseline is not None

        # 4. Fetch investigation details
        get_inv_resp = await async_client.get(f"/api/v1/investigations/{inv_id}")
        assert get_inv_resp.status_code == 200
        parsed_get_inv = InvestigationDetailResponse(**get_inv_resp.json())
        assert parsed_get_inv.investigation_id == inv_id

        # 5. Fetch validated handoff JSON
        handoff_resp = await async_client.get(f"/api/v1/investigations/{inv_id}/handoff")
        assert handoff_resp.status_code == 200
        parsed_handoff = Member1Handoff(**handoff_resp.json())
        assert parsed_handoff.investigation_id == inv_id
        assert parsed_handoff.schema_version == "1.0"
        assert parsed_handoff.optimization_handoff is not None
        assert len(parsed_handoff.optimization_handoff.ranked_hypotheses) > 0


@pytest.mark.asyncio
async def test_api_investigation_not_found():
    """Verify 404 is returned for non-existent investigation ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        resp = await async_client.get("/api/v1/investigations/non-existent-id-999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_api_invalid_image_upload():
    """Verify 400 is returned when corrupt file is uploaded."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        corrupt_file = {"image": ("bad.png", b"CORRUPT_BYTES", "image/png")}
        resp = await async_client.post("/api/v1/architecture/analyze", files=corrupt_file)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "ERR_IMAGE_CORRUPT"


# ============================================================================
# Simulator Integration Endpoints Tests (/api/v1/simulate/...)
# ============================================================================

@pytest.mark.asyncio
async def test_api_simulate_baseline_and_diagnostic():
    """Test Member 2 simulator baseline and diagnostic endpoints directly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        arch_payload = {
            "schema_version": "1.0",
            "architecture_id": "arch-direct-sim-01",
            "components": [
                {"id": "api-1", "type": "api_server", "attributes": {"cpu_cores": 2}},
                {"id": "db-1", "type": "database", "attributes": {"cpu_cores": 2}},
            ],
            "connections": [
                {"source": "api-1", "target": "db-1", "type": "data_access"}
            ],
            "workload": {
                "requests_per_second": 500.0,
                "read_ratio": 0.8,
                "write_ratio": 0.2
            },
            "constraints": {
                "max_p95_latency_ms": 200.0
            }
        }

        # 1. Test POST /api/v1/simulate/baseline
        base_resp = await async_client.post(
            "/api/v1/simulate/baseline",
            json={"run_id": "run-direct-base-01", "architecture": arch_payload},
        )
        assert base_resp.status_code == 200
        parsed_base = BaselineSimulationResponse(**base_resp.json())
        assert parsed_base.run_id == "run-direct-base-01"
        assert parsed_base.source == "member2_simulator"
        assert parsed_base.is_mock is False
        assert parsed_base.metrics["p95_latency_ms"] is not None
        assert parsed_base.metrics["p95_latency_ms"] > 0

        # 2. Test POST /api/v1/simulate/diagnostic
        diag_req = {
            "experiment_id": "exp-direct-01",
            "baseline_run_id": "run-direct-base-01",
            "experiment_type": "increase_workload",
            "target_components": ["db-1"],
            "parameters_to_change": {"multiplier": 1.5},
            "fixed_parameters": {},
            "reason": "Test load increase impact on database",
            "hypotheses_tested": ["HYP-001"],
            "expected_evidence": "Latency increase on database",
        }
        diag_resp = await async_client.post(
            "/api/v1/simulate/diagnostic",
            json=diag_req,
        )
        assert diag_resp.status_code == 200
        parsed_diag = DiagnosticExperimentResponse(**diag_resp.json())
        assert parsed_diag.experiment_id == "exp-direct-01"
        assert parsed_diag.source == "member2_simulator"
        assert parsed_diag.is_mock is False
        assert len(parsed_diag.diff_from_baseline) > 0
