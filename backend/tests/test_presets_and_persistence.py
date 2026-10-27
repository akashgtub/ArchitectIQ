"""
ArchitectIQ - Presets, Persistence, and Security Automated Tests
Verifies preset loading, SQLite persistence of architectures & runs, and image security.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.persistence.repositories import ArchitectureRepository, SimulationRepository
from backend.ai_agent.image_validator import validate_image_bytes, ImageValidationError


@pytest.mark.asyncio
async def test_api_list_presets():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        preset_ids = [p["id"] for p in data["presets"]]
        assert "ecommerce" in preset_ids
        assert "payments" in preset_ids
        assert "cdn_streaming" in preset_ids
        assert "three_tier" in preset_ids


@pytest.mark.asyncio
async def test_api_get_preset_by_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/presets/ecommerce")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ecommerce"
        assert "architecture" in data
        assert len(data["architecture"]["components"]) >= 4

        # Non-existent preset returns 404
        not_found = await client.get("/api/v1/presets/unknown-preset-xyz")
        assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_architecture_persistence_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        test_arch_id = "test-arch-persist-01"
        payload = {
            "id": test_arch_id,
            "name": "Test Persistent System",
            "description": "Integration test persistence model",
            "schema_version": "1.0",
            "data": {
                "architecture_id": test_arch_id,
                "components": [
                    {"id": "lb-1", "type": "load_balancer", "name": "Load Balancer", "capacity_rps": 2000}
                ],
                "connections": []
            }
        }
        create_resp = await client.post("/api/v1/history/architectures", json=payload)
        assert create_resp.status_code == 200

        # Retrieve
        get_resp = await client.get(f"/api/v1/history/architectures/{test_arch_id}")
        assert get_resp.status_code == 200
        arch_data = get_resp.json()
        assert arch_data["id"] == test_arch_id
        assert arch_data["name"] == "Test Persistent System"

        # List
        list_resp = await client.get("/api/v1/history/architectures")
        assert list_resp.status_code == 200
        arch_list = list_resp.json()["architectures"]
        assert any(a["id"] == test_arch_id for a in arch_list)

        # Delete
        del_resp = await client.delete(f"/api/v1/history/architectures/{test_arch_id}")
        assert del_resp.status_code == 200

        # Confirm deleted
        get_after = await client.get(f"/api/v1/history/architectures/{test_arch_id}")
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_simulation_history_persistence():
    import uuid
    run_id = f"test-sim-run-{uuid.uuid4().hex[:8]}"
    SimulationRepository.record_run(
        run_id=run_id,
        architecture_id="arch-ecommerce-01",
        run_type="baseline",
        result={"p95_latency_ms": 42.5, "completed_rps": 1200.0},
        workload={"requests_per_second": 1200}
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_resp = await client.get("/api/v1/history/simulations")
        assert list_resp.status_code == 200
        runs = list_resp.json()["runs"]
        assert any(r["id"] == run_id for r in runs)

        detail_resp = await client.get(f"/api/v1/history/simulations/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == run_id
        assert detail["result"]["p95_latency_ms"] == 42.5


def test_image_security_rejects_empty_and_corrupt():
    with pytest.raises(ImageValidationError) as exc_empty:
        validate_image_bytes(b"")
    assert exc_empty.value.code == "ERR_IMAGE_EMPTY"

    with pytest.raises(ImageValidationError) as exc_corrupt:
        validate_image_bytes(b"CORRUPT_HEADER_NOT_AN_IMAGE_XYZ")
    assert exc_corrupt.value.code == "ERR_IMAGE_CORRUPT"
