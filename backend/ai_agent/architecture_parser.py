"""
ArchPilot AI - Architecture Parser Service
Member 1: Architecture Understanding & Root-Cause Investigation

Coordinates image validation, model-driven architecture extraction,
and strict graph & workload validation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.ai_agent.gemma_client import GemmaClient, ModelClientError
from backend.ai_agent.graph_validator import GraphValidator
from backend.ai_agent.image_validator import ImageValidationError, validate_image_bytes
from backend.shared.schemas import (
    Architecture,
    ArchitectureAnalyzeResponse,
    ArchitectureValidationResult,
    SCHEMA_VERSION,
)

logger = logging.getLogger("archpilot.architecture_parser")


class ArchitectureParserService:
    """
    Main orchestration service for architecture diagram ingestion and validation.
    """

    def __init__(
        self,
        model_client: Optional[GemmaClient] = None,
        graph_validator: Optional[GraphValidator] = None,
    ):
        self.model_client = model_client or GemmaClient()
        self.graph_validator = graph_validator or GraphValidator()

    async def analyze_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        filename: str = "diagram.png",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
    ) -> ArchitectureAnalyzeResponse:
        """
        Ingests image and requirements, validates the image, calls Gemma/Gemini,
        normalizes the topology, and validates the resulting architecture.
        """
        # Step 1: Validate image if provided
        img_format = "PNG"
        if image_bytes:
            width, height, img_format = validate_image_bytes(image_bytes, filename=filename)
            logger.info("Image validated successfully: %dx%d (%s)", width, height, img_format)

        # Step 2: Extract architecture via model client
        raw_extraction = await self.model_client.extract_architecture(
            image_bytes=image_bytes,
            image_format=img_format,
            user_requirements=user_requirements,
            user_workload=user_workload,
            user_constraints=user_constraints,
        )

        arch_id = raw_extraction.get("architecture_id", "arch-unknown")
        direct_obs = raw_extraction.get("direct_observations", [])
        inferred = raw_extraction.get("inferred_elements", [])
        unknown = raw_extraction.get("unknown_elements", [])
        raw_clarifications = raw_extraction.get("clarification_questions", [])

        # Step 3: Graph and schema validation
        validation_result = self.graph_validator.validate_architecture(
            arch_data=raw_extraction,
            raw_clarifications=raw_clarifications,
            raw_assumptions=inferred,
        )

        # Step 4: Construct verified Architecture object if valid
        architecture_obj: Optional[Architecture] = None
        status = "validation_failed"
        if validation_result.valid:
            try:
                # Ensure schema_version is present
                raw_extraction["schema_version"] = raw_extraction.get("schema_version", SCHEMA_VERSION)
                architecture_obj = Architecture(**raw_extraction)
                status = "validated"
            except Exception as e:
                logger.warning("Pydantic architecture construction failed: %s", e)
                validation_result.valid = False
                status = "validation_failed"

        provider_obj = getattr(self.model_client, "provider", None)
        is_fallback = (
            self.model_client.use_mock
            or bool(raw_extraction.get("fallback_used"))
            or (provider_obj and provider_obj.name == "deterministic_fallback")
        )
        provider_name = "deterministic_fallback" if is_fallback else (provider_obj.name if provider_obj else "gemma")

        return ArchitectureAnalyzeResponse(
            architecture_id=arch_id,
            status=status,
            architecture=architecture_obj,
            validation=validation_result,
            direct_observations=direct_obs,
            inferred_elements=inferred,
            unknown_elements=unknown,
            model_id="mock-extractor" if self.model_client.use_mock else self.model_client.model_id,
            is_mock=self.model_client.use_mock,
            execution_mode="mock" if is_fallback else "real",
            fallback_used=is_fallback,
            provider=provider_name,
            request_id=str(raw_extraction.get("request_id") or "req-arch-001"),
        )
