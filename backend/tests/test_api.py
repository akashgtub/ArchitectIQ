"""
Tests for API Routes and End-to-End Workflow
Covers:
- Case 20: API responses conform to agreed response schemas.
- End-to-end integration flow through HTTP client:
  * Health check
  * Architecture analyze endpoint
  * Start investigation endpoint
  * Get investigation endpoint
  * Get handoff endpoint
"""

import io
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.main import app
from backend.shared.schemas import (
    ArchitectureAnalyzeResponse,
    InvestigationDetailResponse,
    Member1Handoff,
)


def create_dummy_png_bytes(width: int = 150, height: int = 150) -> bytes:
    img = Image.new("RGB", (width, height), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_case_20_api_responses_conform_to_schema():
    """Case 20: API response uses the agreed response schema across all endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        health_resp = await client.get("/health")
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

        analyze_resp = await client.post("/api/v1/architecture/analyze", data=data, files=files)
        assert analyze_resp.status_code == 200
        parsed_analyze = ArchitectureAnalyzeResponse(**analyze_resp.json())
        assert parsed_analyze.status == "validated"
        assert parsed_analyze.architecture is not None

        # 3. Start investigation
        arch_payload = parsed_analyze.architecture.model_dump()
        inv_resp = await client.post(
            "/api/v1/investigations",
            json={"architecture": arch_payload, "max_diagnostic_experiments": 2},
        )
        assert inv_resp.status_code == 201
        parsed_inv = InvestigationDetailResponse(**inv_resp.json())
        inv_id = parsed_inv.investigation_id
        assert parsed_inv.handoff_ready is True
        assert parsed_inv.baseline is not None

        # 4. Fetch investigation details
        get_inv_resp = await client.get(f"/api/v1/investigations/{inv_id}")
        assert get_inv_resp.status_code == 200
        parsed_get_inv = InvestigationDetailResponse(**get_inv_resp.json())
        assert parsed_get_inv.investigation_id == inv_id

        # 5. Fetch validated handoff JSON
        handoff_resp = await client.get(f"/api/v1/investigations/{inv_id}/handoff")
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
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/investigations/non-existent-id-999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_api_invalid_image_upload():
    """Verify 400 is returned when corrupt file is uploaded."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        corrupt_file = {"image": ("bad.png", b"CORRUPT_BYTES", "image/png")}
        resp = await client.post("/api/v1/architecture/analyze", files=corrupt_file)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "ERR_IMAGE_CORRUPT"
