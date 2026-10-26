"""
ArchPilot AI - Gemma / Gemini API Model Client
Member 1: Architecture Understanding & Root-Cause Investigation

Handles structured extraction of architecture diagrams using Google Gemini API
(including Gemma and Gemini models).
Distinguishes between directly observed, user-provided, inferred, and unknown info.
Supports bounded retries, structured JSON extraction, and deterministic mock mode
for testing and offline execution.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.shared.schemas import (
    ComponentType,
    ConnectionType,
    SCHEMA_VERSION,
)

logger = logging.getLogger("archpilot.gemma_client")

EXTRACTION_SYSTEM_INSTRUCTION = """You are an expert distributed systems architect analyzing an architecture diagram image.
Your task is to extract an exact, structured architecture representation without hallucinating components or unstated specifications.

CRITICAL RULES:
1. Distinguish between:
   - "directly_observed": Elements with explicit visual shapes or text labels in the diagram.
   - "inferred": Assumptions made based on standard system design patterns (e.g., protocol assumed as HTTP).
   - "unknown": Information missing from diagram (e.g., queue size, DB capacity, cache TTL).
2. Allowed component types:
   api_server, web_server, load_balancer, database, cache, message_queue, object_storage, microservice, gateway, worker, cdn, external_service, unknown
3. Allowed connection types:
   request (sync), async_message (queue/pubsub), data_access (DB/cache), dependency (health/config), stream (websocket/kafka)
4. Do NOT invent throughput, latency, or workload values if not explicitly visible or provided.
5. If important information is missing or ambiguous, output clear clarification questions.

Return your response in STRICT, VALID JSON following this exact structure:
{
  "architecture_id": "arch-extracted-001",
  "components": [
    {
      "id": "comp-id",
      "type": "component_type",
      "name": "Visible Name",
      "attributes": {}
    }
  ],
  "connections": [
    {
      "source": "comp-id-1",
      "target": "comp-id-2",
      "type": "request",
      "attributes": {}
    }
  ],
  "workload": {
    "requests_per_second": 1000.0,
    "read_ratio": 0.8,
    "write_ratio": 0.2
  },
  "constraints": {
    "max_p95_latency_ms": 200.0,
    "min_throughput_rps": null,
    "max_cost_per_hour": null,
    "min_availability": null
  },
  "direct_observations": ["list of directly observed visual elements"],
  "inferred_elements": ["list of assumptions made"],
  "unknown_elements": ["list of missing details"],
  "clarification_questions": [
    {
      "question_id": "Q-001",
      "question": "What is the expected read/write workload split?",
      "affected_components": ["db-1"],
      "category": "workload",
      "suggested_options": ["80% read / 20% write", "50% read / 50% write", "Write-heavy (90% write)"]
    }
  ]
}
"""


from backend.ai_agent.providers import (
    BaseAIProvider,
    DeterministicFallbackProvider,
    GeminiProvider,
    GemmaProvider,
    HuggingFaceProvider,
    ModelClientError,
    get_ai_provider,
)


class GemmaClient:
    """
    Client for interacting with Google Gemma / Gemini API models and Hugging Face Inference Providers.
    Supports clean BaseAIProvider abstraction, bounded retries,
    structured JSON extraction, and explicit transparent mock fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        use_mock: Optional[bool] = None,
        provider: Optional[BaseAIProvider] = None,
    ):
        if provider:
            self.provider = provider
            self.api_key = getattr(provider, "api_key", getattr(provider, "api_token", api_key or settings.gemini_api_key))
            self.model_id = provider.model_name
            self.use_mock = provider.name == "deterministic_fallback"
        else:
            self.api_key = api_key if api_key is not None else (settings.gemma_api_key or settings.gemini_api_key or settings.hf_token)
            self.model_id = model_id if model_id is not None else (
                settings.hf_model if settings.ai_provider in ("huggingface", "hf") else (
                    settings.gemma_model_id if "gemma" in (settings.ai_provider or "") else settings.gemini_model_id
                )
            )
            if use_mock is not None:
                self.use_mock = use_mock
            else:
                self.use_mock = not bool(self.api_key or settings.gemma_base_url or settings.hf_token)

            if self.use_mock:
                self.provider = DeterministicFallbackProvider()
            elif settings.ai_provider in ("huggingface", "hf"):
                self.provider = HuggingFaceProvider(
                    api_token=settings.hf_token,
                    model_id=settings.hf_model,
                    base_url=settings.hf_base_url,
                )
            elif "gemma" in self.model_id.lower() or settings.gemma_base_url or settings.ai_provider == "gemma":
                self.provider = GemmaProvider(api_key=self.api_key, model_id=self.model_id, base_url=settings.gemma_base_url)
            else:
                self.provider = GeminiProvider(api_key=self.api_key, model_id=self.model_id, base_url=settings.gemini_base_url)

        self._genai_client = None

    async def extract_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts structured architecture from image and requirements.
        Uses the configured AI provider with bounded retries.
        If image_bytes is provided and current provider is text-only,
        routes image extraction to a vision-capable provider.
        """
        if self.use_mock or self.provider.name == "deterministic_fallback":
            return self._generate_mock_extraction(
                user_requirements=user_requirements,
                user_workload=user_workload,
                user_constraints=user_constraints,
            )

        target_provider = self.provider
        if image_bytes and not self.provider.supports_vision:
            logger.info(
                "Active provider '%s' is text-only. Routing image parsing to vision-capable provider.",
                self.provider.name,
            )
            target_provider = get_ai_provider(task="vision")

        try:
            return await target_provider.extract_architecture(
                image_bytes=image_bytes,
                image_format=image_format,
                user_requirements=user_requirements,
                user_workload=user_workload,
                user_constraints=user_constraints,
            )
        except ModelClientError:
            raise
        except Exception as e:
            logger.warning("AI provider extraction failed: %s", e)
            raise ModelClientError(
                f"Failed to extract architecture via provider '{target_provider.name}': {e}",
                code="ERR_MODEL_EXTRACTION_FAILED",
            )

    async def _call_model_with_image(
        self,
        image_bytes: Optional[bytes],
        image_format: str,
        user_requirements: Optional[str],
        user_workload: Optional[Dict[str, Any]],
        user_constraints: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calls live Gemini API.
        """
        prompt = EXTRACTION_SYSTEM_INSTRUCTION
        if user_requirements:
            prompt += f"\n\nUSER REQUIREMENTS:\n{user_requirements}"
        if user_workload:
            prompt += f"\n\nPROVIDED WORKLOAD:\n{json.dumps(user_workload, indent=2)}"
        if user_constraints:
            prompt += f"\n\nPROVIDED CONSTRAINTS:\n{json.dumps(user_constraints, indent=2)}"

        mime_type = f"image/{image_format.lower()}"
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"

        if self._genai_client:
            from google.genai import types

            contents = [prompt]
            if image_bytes:
                contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                )

            response = self._genai_client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text or ""
            return self._parse_json_response(raw_text)
        else:
            # Fallback to direct HTTP call via httpx
            return await self._call_gemini_rest(
                prompt=prompt,
                image_bytes=image_bytes,
                mime_type=mime_type,
            )

    async def _call_gemini_rest(
        self,
        prompt: str,
        image_bytes: Optional[bytes],
        mime_type: str,
    ) -> Dict[str, Any]:
        import base64
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"
        parts: List[Dict[str, Any]] = [{"text": prompt}]

        if image_bytes:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data,
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=settings.per_call_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise ModelClientError(
                    f"Gemini API returned HTTP {resp.status_code}: {resp.text}",
                    code="ERR_GEMINI_API_HTTP",
                )
            data = resp.json()
            try:
                candidate = data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_json_response(candidate)
            except (KeyError, IndexError) as err:
                raise ModelClientError(
                    f"Malformed response structure from Gemini API: {err}",
                    code="ERR_GEMINI_MALFORMED_RESPONSE",
                )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Strips markdown code blocks if present and parses JSON safely.
        """
        cleaned = text.strip()
        # Remove ```json ... ``` wrapper if present
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if json_match:
            cleaned = json_match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise ValueError("Parsed JSON root is not a dictionary")
            return parsed
        except Exception as e:
            raise ModelClientError(
                f"Failed to parse model response as JSON: {e}. Raw content: {cleaned[:200]}...",
                code="ERR_INVALID_MODEL_JSON",
            )

    def _generate_mock_extraction(
        self,
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Deterministic mock architecture extraction for unit tests and local testing.
        Explicitly documents components, connections, workload, and assumptions.
        """
        # Determine workload
        rps = 1000.0
        read_r = 0.8
        write_r = 0.2
        if user_workload:
            rps = float(user_workload.get("requests_per_second", rps))
            read_r = float(user_workload.get("read_ratio", read_r))
            write_r = float(user_workload.get("write_ratio", write_r))

        # Determine constraints
        max_p95 = 200.0
        min_rps = None
        max_cost = None
        min_avail = 0.999
        if user_constraints:
            max_p95 = user_constraints.get("max_p95_latency_ms", max_p95)
            min_rps = user_constraints.get("min_throughput_rps", min_rps)
            max_cost = user_constraints.get("max_cost_per_hour", max_cost)
            min_avail = user_constraints.get("min_availability", min_avail)

        return {
            "schema_version": SCHEMA_VERSION,
            "architecture_id": "arch-mock-extracted-001",
            "components": [
                {
                    "id": "gateway-1",
                    "type": ComponentType.GATEWAY.value,
                    "name": "API Gateway",
                    "attributes": {"instances": 2, "protocol": "HTTPS"}
                },
                {
                    "id": "api-service",
                    "type": ComponentType.API_SERVER.value,
                    "name": "Order API Service",
                    "attributes": {"instances": 4, "cpu_cores": 2, "ram_gb": 4}
                },
                {
                    "id": "redis-cache",
                    "type": ComponentType.CACHE.value,
                    "name": "Redis Session Cache",
                    "attributes": {"engine": "redis", "capacity_mb": 2048, "ttl_seconds": 3600}
                },
                {
                    "id": "db-primary",
                    "type": ComponentType.DATABASE.value,
                    "name": "Postgres Primary",
                    "attributes": {"engine": "postgresql", "max_connections": 100, "storage_gb": 200}
                }
            ],
            "connections": [
                {
                    "source": "gateway-1",
                    "target": "api-service",
                    "type": ConnectionType.REQUEST.value,
                    "attributes": {"protocol": "HTTP/1.1", "timeout_ms": 3000}
                },
                {
                    "source": "api-service",
                    "target": "redis-cache",
                    "type": ConnectionType.DATA_ACCESS.value,
                    "attributes": {"protocol": "RESP", "timeout_ms": 100}
                },
                {
                    "source": "api-service",
                    "target": "db-primary",
                    "type": ConnectionType.DATA_ACCESS.value,
                    "attributes": {"protocol": "TCP/Postgres", "pool_size": 20}
                }
            ],
            "workload": {
                "requests_per_second": rps,
                "read_ratio": read_r,
                "write_ratio": write_r,
                "peak_multiplier": 1.5,
                "concurrent_users": 500
            },
            "constraints": {
                "max_p95_latency_ms": max_p95,
                "min_throughput_rps": min_rps,
                "max_cost_per_hour": max_cost,
                "min_availability": min_avail
            },
            "direct_observations": [
                "Observed 4 primary nodes: API Gateway, Order API Service, Redis Cache, Postgres Primary",
                "Observed bidirectional data connections from API Service to Redis and Postgres",
                "Observed single ingress gateway component"
            ],
            "inferred_elements": [
                "Inferred connection between gateway and API service uses HTTP/1.1",
                "Assumed cache lookups occur prior to database queries"
            ],
            "unknown_elements": [
                "Cache eviction policy (LRU vs LFU) not specified in diagram",
                "Database replication topology (read replicas) not visible in diagram"
            ],
            "clarification_questions": [
                {
                    "question_id": "Q-CACHE-POLICY",
                    "question": "What is the cache eviction policy and expected cache hit ratio?",
                    "affected_components": ["redis-cache"],
                    "category": "cache_policy",
                    "suggested_options": ["LRU with ~80% hit ratio", "No eviction (in-memory only)", "Write-through"]
                }
            ]
        }
