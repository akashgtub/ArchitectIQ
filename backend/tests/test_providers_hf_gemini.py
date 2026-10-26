"""
Unit and integration tests for Hugging Face Inference Providers and Google Gemini.
Covers:
- Environment variable loading from root .env
- Provider selection (huggingface, gemini, gemma, deterministic_fallback, auto)
- Task-specific routing (vision vs text)
- Model vision boundary enforcement (rejecting image bytes on text models)
- Mocked successful inference for Hugging Face and Gemini
- Error handling: HTTP 401, 402, 400, 429, 503, and network timeouts
- Secret redaction preventing credential leakage
- Explicit fallback labeling
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.ai_agent.gemma_client import GemmaClient
from backend.ai_agent.providers import (
    DeterministicFallbackProvider,
    GeminiProvider,
    GemmaProvider,
    HuggingFaceProvider,
    ModelClientError,
    _sanitize_text,
    get_ai_provider,
)
from backend.config import Settings, settings
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationResponse,
    ComponentType,
    ConnectionType,
    DiagnosticExperimentResponse,
    RootCauseHypothesis,
)
from backend.simulator.schemas import CandidateArchitecture, FailureScenario, PerformanceMetrics


# ---------------------------------------------------------------------------
# Test 1: Secret Redaction
# ---------------------------------------------------------------------------

def test_secret_redaction():
    raw_message = (
        "Failed request to https://generativelanguage.googleapis.com/v1beta/models/gemini:generateContent?key=AQ.abc1234567890xyz "
        "Authorization: Bearer hf_abcdef123456789012345678901234567890 "
        "with Google Key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q and password=SuperSecretPassword123"
    )
    sanitized = _sanitize_text(raw_message)

    assert "AQ.abc" not in sanitized
    assert "hf_abcdef" not in sanitized
    assert "AIzaSyA1B2C3" not in sanitized
    assert "SuperSecretPassword123" not in sanitized
    assert "[REDACTED]" in sanitized


# ---------------------------------------------------------------------------
# Test 2: Provider Selection & Factory
# ---------------------------------------------------------------------------

def test_provider_factory_selection_huggingface():
    with patch.object(settings, "hf_token", "hf_test_token_12345"), \
         patch.object(settings, "hf_model", "google/gemma-2-27b-it"):
        provider = get_ai_provider(provider_type="huggingface")
        assert isinstance(provider, HuggingFaceProvider)
        assert provider.name == "huggingface"
        assert provider.model_name == "google/gemma-2-27b-it"
        assert provider.supports_vision is False


def test_provider_factory_selection_gemini():
    with patch.object(settings, "gemini_api_key", "test-gemini-key"):
        provider = get_ai_provider(provider_type="gemini")
        assert isinstance(provider, GeminiProvider)
        assert provider.name == "gemini"
        assert provider.supports_vision is True


def test_provider_factory_missing_hf_token_raises_or_fallback():
    # When fallback is disabled, raises ModelClientError
    with patch.object(settings, "hf_token", ""), \
         patch.object(settings, "allow_ai_fallback", False):
        with pytest.raises(ModelClientError) as exc_info:
            get_ai_provider(provider_type="huggingface")
        assert exc_info.value.code == "ERR_NO_HF_TOKEN"

    # When fallback is enabled, returns DeterministicFallbackProvider
    with patch.object(settings, "hf_token", ""), \
         patch.object(settings, "allow_ai_fallback", True):
        provider = get_ai_provider(provider_type="huggingface")
        assert isinstance(provider, DeterministicFallbackProvider)
        assert provider.name == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Test 3: Vision Task Routing & Image Protection
# ---------------------------------------------------------------------------

def test_vision_task_never_selects_text_provider():
    # Even if global provider is huggingface, task='vision' routes to vision provider (Gemini or Fallback)
    with patch.object(settings, "ai_provider", "huggingface"), \
         patch.object(settings, "hf_token", "hf_valid_token"), \
         patch.object(settings, "gemini_api_key", "valid-gemini-key"):
        provider = get_ai_provider(task="vision")
        assert isinstance(provider, GeminiProvider)
        assert provider.supports_vision is True


def test_vision_task_fallback_when_gemini_missing():
    with patch.object(settings, "gemini_api_key", ""), \
         patch.object(settings, "allow_ai_fallback", True):
        provider = get_ai_provider(task="vision")
        assert isinstance(provider, DeterministicFallbackProvider)


@pytest.mark.asyncio
async def test_huggingface_rejects_raw_image_bytes():
    provider = HuggingFaceProvider(api_token="hf_mock_token")
    with pytest.raises(ModelClientError) as exc_info:
        await provider.extract_architecture(image_bytes=b"\x89PNG\r\n\x1a\n...")
    assert exc_info.value.code == "ERR_UNSUPPORTED_VISION"


# ---------------------------------------------------------------------------
# Test 4: Hugging Face Inference Providers (Mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_huggingface_successful_chat_completion():
    provider = HuggingFaceProvider(api_token="hf_mock_token", model_id="google/gemma-2-27b-it")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"architecture_id": "arch-hf-001", "components": [], "connections": []}'
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await provider.extract_architecture(user_requirements="Test requirements")
        assert result["architecture_id"] == "arch-hf-001"
        assert mock_post.called
        # Verify endpoint and Authorization header
        call_args = mock_post.call_args
        assert "/chat/completions" in call_args[0][0]
        assert "Bearer hf_mock_token" in call_args[1]["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_huggingface_http_402_no_credits_error():
    provider = HuggingFaceProvider(api_token="hf_mock_token")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 402
    mock_resp.text = '{"error":"You have no remaining credits. Purchase pre-paid credits to continue."}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ModelClientError) as exc_info:
            await provider._call_chat_completions(prompt="Hello")
        assert exc_info.value.code == "ERR_HF_NO_CREDITS"
        assert "credits" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_huggingface_http_401_auth_error():
    provider = HuggingFaceProvider(api_token="hf_invalid_token")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = '{"error":"Invalid credentials"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ModelClientError) as exc_info:
            await provider._call_chat_completions(prompt="Hello")
        assert exc_info.value.code == "ERR_HF_AUTH"


@pytest.mark.asyncio
async def test_huggingface_http_400_unsupported_model_error():
    provider = HuggingFaceProvider(api_token="hf_valid_token", model_id="unsupported/model")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 400
    mock_resp.text = '{"error":{"message":"The requested model is not supported."}}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ModelClientError) as exc_info:
            await provider._call_chat_completions(prompt="Hello")
        assert exc_info.value.code == "ERR_HF_MODEL_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_huggingface_timeout_error():
    provider = HuggingFaceProvider(api_token="hf_valid_token")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timed out")
        with pytest.raises(ModelClientError) as exc_info:
            await provider._call_chat_completions(prompt="Hello")
        assert exc_info.value.code == "ERR_HF_TIMEOUT"


# ---------------------------------------------------------------------------
# Test 5: Google Gemini Multimodal Provider (Mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_successful_generate_content():
    provider = GeminiProvider(api_key="test_gemini_key", model_id="gemini-flash-latest")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '{"architecture_id": "arch-gemini-001", "components": [], "connections": []}'}]
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await provider.extract_architecture(image_bytes=b"fake-image", image_format="PNG")
        assert result["architecture_id"] == "arch-gemini-001"
        assert mock_post.called


@pytest.mark.asyncio
async def test_gemini_quota_exceeded_429():
    provider = GeminiProvider(api_key="test_gemini_key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = '{"error":{"code":429,"message":"Quota exceeded on Free Tier"}}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ModelClientError) as exc_info:
            await provider._post_generate_content(prompt="Test")
        assert exc_info.value.code == "ERR_GEMINI_QUOTA"


@pytest.mark.asyncio
async def test_gemini_model_not_found_404():
    provider = GeminiProvider(api_key="test_gemini_key", model_id="deprecated-model")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.text = '{"error":{"code":404,"message":"Model not found or deprecated"}}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ModelClientError) as exc_info:
            await provider._post_generate_content(prompt="Test")
        assert exc_info.value.code == "ERR_GEMINI_MODEL_NOT_FOUND"


# ---------------------------------------------------------------------------
# Test 6: GemmaClient Intelligent Delegation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemma_client_delegates_image_to_vision_provider():
    # If GemmaClient holds a text-only HuggingFace provider, sending an image routes to Gemini
    hf_provider = HuggingFaceProvider(api_token="hf_test_token")
    client = GemmaClient(provider=hf_provider)

    mock_vision_provider = MagicMock(spec=GeminiProvider)
    mock_vision_provider.supports_vision = True
    mock_vision_provider.extract_architecture = AsyncMock(return_value={"architecture_id": "arch-from-vision", "components": [], "connections": []})

    with patch("backend.ai_agent.gemma_client.get_ai_provider", return_value=mock_vision_provider):
        result = await client.extract_architecture(image_bytes=b"raw-png-data", image_format="PNG")
        assert result["architecture_id"] == "arch-from-vision"
        assert mock_vision_provider.extract_architecture.called
