"""Integration tests for standalone FastAPI endpoints using TestClient."""

import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import router

# Mount the standalone router on a lightweight test application
app = FastAPI(title="ArchitectIQ Test Server")
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def sample_payload() -> dict:
    """Load sample architecture fixture as a JSON dictionary."""
    path = Path(__file__).resolve().parent.parent / "examples" / "sample_architecture.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Use shorter duration for fast test execution
    data["workload"]["duration_seconds"] = 10.0
    return data


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
    # Must dump and re-parse without error
    json_text = json.dumps(resp.json())
    assert len(json_text) > 0
    assert "NaN" not in json_text
    assert "Infinity" not in json_text
