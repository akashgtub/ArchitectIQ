"""
PyTest Configuration & Test Isolation
Ensures external paid AI APIs (Hugging Face / Google Gemini) are not called
accidentally during automated unit and integration tests.
"""

import pytest
from backend.config import settings


@pytest.fixture(autouse=True)
def isolate_external_ai_apis_in_tests(request, monkeypatch):
    """
    Isolates external third-party API calls during tests unless the test
    explicitly tests provider interactions with mocked or configured clients.
    """
    test_name = request.node.name
    test_file = str(request.node.fspath) if hasattr(request.node, "fspath") else ""

    # Legacy unit tests designed around deterministic mock outputs
    if any(f in test_file for f in ("test_architecture_parser.py", "test_api.py", "test_root_cause.py")):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        monkeypatch.setattr(settings, "hf_token", "")
        monkeypatch.setattr(settings, "gemma_api_key", "")
        monkeypatch.setattr(settings, "gemma_base_url", "")
