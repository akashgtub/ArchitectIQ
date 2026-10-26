"""
ArchPilot AI - Backend Configuration
Member 1: Architecture Understanding & Root-Cause Investigation

Manages environment variables, model identifiers, security limits,
and operational parameters.
"""

from __future__ import annotations

import os
from typing import List
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Gemini / Gemma Model Configuration
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    # Default model with multimodal vision + structured JSON output capability
    # Can be set to 'gemini-2.0-flash', 'gemini-1.5-flash', or 'gemma-2-27b-it' (text-only)
    gemini_model_id: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")
    )
    gemini_base_url: str = Field(
        default_factory=lambda: os.getenv("GEMINI_BASE_URL", "")
    )

    # Simulator Integration (Member 2 Engine)
    simulator_base_url: str = Field(
        default_factory=lambda: os.getenv("SIMULATOR_BASE_URL", "")
    )
    simulator_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("SIMULATOR_TIMEOUT_SECONDS", "30"))
    )
    use_mock_simulator: bool = Field(
        default_factory=lambda: os.getenv("USE_MOCK_SIMULATOR", "true").lower() in ("true", "1", "yes")
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
        default_factory=lambda: int(os.getenv("PER_CALL_TIMEOUT_SECONDS", "30"))
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
