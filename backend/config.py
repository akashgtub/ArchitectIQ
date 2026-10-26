"""
ArchPilot AI - Backend Configuration
Member 1: Architecture Understanding & Root-Cause Investigation

Manages environment variables, model identifiers, security limits,
and operational parameters.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

# Automatically load root .env file if available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
    else:
        load_dotenv()
except ImportError:
    pass


class Settings(BaseModel):
    # AI Provider & Model Configuration
    # Options: 'auto', 'huggingface', 'gemini', 'gemma', 'deterministic_fallback'
    ai_provider: str = Field(
        default_factory=lambda: os.getenv("AI_PROVIDER", "auto").lower()
    )
    # Optional task-specific provider overrides
    vision_ai_provider: str = Field(
        default_factory=lambda: os.getenv("VISION_AI_PROVIDER", "gemini").lower()
    )
    text_ai_provider: str = Field(
        default_factory=lambda: os.getenv("TEXT_AI_PROVIDER", os.getenv("AI_PROVIDER", "auto")).lower()
    )

    # Google Gemini Configuration (Multimodal Vision + Reasoning)
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    gemini_model_id: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL_ID", "gemini-flash-latest")
    )
    gemini_base_url: str = Field(
        default_factory=lambda: os.getenv("GEMINI_BASE_URL", "")
    )

    # Hugging Face Inference Providers Configuration (OpenAI-compatible /v1/chat/completions)
    hf_token: str = Field(
        default_factory=lambda: os.getenv("HF_TOKEN", "")
    )
    hf_model: str = Field(
        default_factory=lambda: os.getenv("HF_MODEL", "google/gemma-2-27b-it")
    )
    hf_base_url: str = Field(
        default_factory=lambda: os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1").rstrip("/")
    )

    # Google Gemma Model Configuration (Direct Google API / Custom Host)
    # Supports Google AI Studio, Vertex AI, or OpenAI-compatible inference servers (vLLM, Ollama, Groq)
    gemma_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMMA_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    )
    gemma_model_id: str = Field(
        default_factory=lambda: os.getenv("GEMMA_MODEL_ID", "gemma-2-27b-it")
    )
    gemma_base_url: str = Field(
        default_factory=lambda: os.getenv("GEMMA_BASE_URL", "")
    )
    allow_ai_fallback: bool = Field(
        default_factory=lambda: os.getenv("ALLOW_AI_FALLBACK", "true").lower() in ("true", "1", "yes")
    )

    # Simulator Integration (Member 2 Real Engine)
    # Default is real simulation engine (use_mock_simulator=False).
    # Mock mode is only active when explicitly selected (USE_MOCK_SIMULATOR=true).
    simulator_base_url: str = Field(
        default_factory=lambda: os.getenv("SIMULATOR_BASE_URL", "")
    )
    simulator_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("SIMULATOR_TIMEOUT_SECONDS", "30"))
    )
    use_mock_simulator: bool = Field(
        default_factory=lambda: os.getenv("USE_MOCK_SIMULATOR", "false").lower() in ("true", "1", "yes")
    )

    # Root-Cause Investigation Budget Limits
    max_diagnostic_experiments: int = Field(
        default_factory=lambda: int(os.getenv("MAX_DIAGNOSTIC_EXPERIMENTS", "3"))
    )
    investigation_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("INVESTIGATION_TIMEOUT_SECONDS", "60"))
    )
    max_model_calls: int = Field(
        default_factory=lambda: int(os.getenv("MAX_MODEL_CALLS", "5"))
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "2"))
    )
    per_call_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("PER_CALL_TIMEOUT_SECONDS", "10"))
    )

    # Image Validation Constraints
    max_image_size_bytes: int = Field(
        default_factory=lambda: int(os.getenv("MAX_IMAGE_SIZE_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    )
    max_image_dimension: int = Field(
        default_factory=lambda: int(os.getenv("MAX_IMAGE_DIMENSION", "4096"))
    )
    allowed_image_formats: List[str] = Field(
        default=["PNG", "JPEG", "JPG", "WEBP"]
    )
    # Environment & Security
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    )


settings = Settings()
