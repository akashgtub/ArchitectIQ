"""
Tests for Architecture Parser and Model Extraction
Covers:
- Case 1: Valid architecture extraction response.
- Case 2: Malformed model JSON.
- Case 7: Ambiguous diagram requiring clarification.
- Image ingestion and corrupt file handling.
"""

import io
import pytest
from PIL import Image

from backend.ai_agent.architecture_parser import ArchitectureParserService
from backend.ai_agent.gemma_client import GemmaClient, ModelClientError
from backend.ai_agent.image_validator import ImageValidationError, validate_image_bytes
from backend.shared.schemas import ComponentType, ValidationSeverity


def create_dummy_png_bytes(width: int = 200, height: int = 200, color: str = "blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_case_1_valid_architecture_extraction():
    """Case 1: Valid architecture extraction response."""
    parser = ArchitectureParserService()
    png_bytes = create_dummy_png_bytes()

    response = await parser.analyze_architecture(
        image_bytes=png_bytes,
        filename="system_design.png",
        user_requirements="E-commerce checkout system handling 1000 RPS",
    )

    assert response.status == "validated"
    assert response.architecture is not None
    assert response.architecture.architecture_id == "arch-mock-extracted-001"
    assert len(response.architecture.components) == 4
    assert len(response.architecture.connections) == 3
    assert response.validation.valid is True
    assert len(response.direct_observations) > 0


def test_case_2_malformed_model_json():
    """Case 2: Malformed model JSON is rejected with clear error."""
    client = GemmaClient(use_mock=True)

    # Directly test parsing invalid JSON string
    malformed_raw = "```json\n{ architecture_id: broken, components: [ incomplete"
    with pytest.raises(ModelClientError) as exc_info:
        client._parse_json_response(malformed_raw)

    assert exc_info.value.code == "ERR_INVALID_MODEL_JSON"


@pytest.mark.asyncio
async def test_case_7_ambiguous_diagram_requiring_clarification():
    """Case 7: Ambiguous diagram requiring clarification surfaces questions instead of hallucinating."""
    parser = ArchitectureParserService()
    png_bytes = create_dummy_png_bytes()

    response = await parser.analyze_architecture(
        image_bytes=png_bytes,
        filename="system_design.png",
    )

    # In mock mode, cache policy is unknown and clarification is surfaced
    assert len(response.validation.unresolved_questions) > 0
    question = response.validation.unresolved_questions[0]
    assert question.question_id == "Q-CACHE-POLICY"
    assert "cache" in question.category
    assert question.suggested_options is not None
    assert len(response.unknown_elements) > 0


def test_image_validation_corrupt_file():
    """Rejects corrupt image bytes with ImageValidationError."""
    corrupt_bytes = b"NOT_AN_IMAGE_HEADER_DATA_12345"
    with pytest.raises(ImageValidationError) as exc:
        validate_image_bytes(corrupt_bytes)
    assert exc.value.code == "ERR_IMAGE_CORRUPT"


def test_image_validation_dimension_limits():
    """Rejects images smaller than 10x10."""
    tiny_bytes = create_dummy_png_bytes(width=5, height=5)
    with pytest.raises(ImageValidationError) as exc:
        validate_image_bytes(tiny_bytes)
    assert exc.value.code == "ERR_IMAGE_TOO_SMALL"


@pytest.mark.asyncio
async def test_case_23_configuration_no_model_api_key():
    """Case 23: When no API key is configured, client uses deterministic mock mode with transparent provenance."""
    client = GemmaClient(api_key="", use_mock=None)
    assert client.use_mock is True

    parser = ArchitectureParserService(model_client=client)
    res = await parser.analyze_architecture()
    assert res.is_mock is True
    assert res.model_id == "mock-extractor"
    assert res.status == "validated"


@pytest.mark.asyncio
async def test_case_24_invalid_model_credentials_or_api_error(monkeypatch):
    """Case 24: Invalid model credentials or API error raises ModelClientError with explicit code."""
    import httpx
    client = GemmaClient(api_key="invalid-api-key-12345", use_mock=False)

    class Mock401Response:
        status_code = 401
        text = "API key not valid. Please pass a valid API key."
        def json(self):
            return {"error": {"code": 401, "message": "API key not valid."}}

    async def mock_post(*args, **kwargs):
        return Mock401Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with pytest.raises(ModelClientError) as exc_info:
        await client._call_gemini_rest(prompt="test prompt", image_bytes=None, mime_type="image/png")

    assert exc_info.value.code == "ERR_GEMINI_API_HTTP"
    assert "401" in exc_info.value.message
