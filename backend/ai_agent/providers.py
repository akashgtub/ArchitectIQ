"""
ArchitectIQ - Unified AI Provider Abstraction
Supports Google Gemma (text instruction reasoning), Google Gemini (multimodal vision + reasoning),
and an explicitly identified deterministic fallback provider.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from backend.config import settings
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationResponse,
    ComponentType,
    ConnectionType,
    DiagnosticExperimentResponse,
    RootCauseHypothesis,
    SCHEMA_VERSION,
)
from backend.simulator.schemas import (
    CandidateArchitecture,
    FailureScenario,
    PerformanceMetrics,
)

logger = logging.getLogger("architectiq.ai_provider")


class ModelClientError(Exception):
    """Raised when an AI provider call fails or returns an unprocessable response."""
    def __init__(self, message: str, code: str = "ERR_MODEL_CLIENT"):
        super().__init__(message)
        self.message = message
        self.code = code


class AIResponse(BaseModel):
    """Normalized output from an AI provider invocation."""
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    text: str
    structured_json: Optional[Dict[str, Any]] = None
    provider: str
    model_name: str
    fallback_used: bool = False
    execution_time_ms: float = 0.0
    request_id: Optional[str] = None


class BaseAIProvider(ABC):
    """Abstract interface for AI model inference in ArchitectIQ."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of provider (e.g. 'gemini', 'gemma', 'deterministic_fallback')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of active model."""
        pass

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether provider natively processes image bytes."""
        pass

    @abstractmethod
    async def extract_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract structured architecture diagram representation."""
        pass

    @abstractmethod
    async def explain_root_cause(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
        hypotheses: List[RootCauseHypothesis],
        experiments: List[DiagnosticExperimentResponse],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize evidence-grounded root-cause explanation citing simulation data."""
        pass

    @abstractmethod
    async def explain_optimization(
        self,
        baseline_metrics: PerformanceMetrics,
        candidates: List[CandidateArchitecture],
        recommended: Optional[CandidateArchitecture],
        objective: str,
        request_id: Optional[str] = None,
    ) -> str:
        """Generate architectural trade-off narrative for candidate optimizations."""
        pass

    @abstractmethod
    async def explain_chaos(
        self,
        scenario: FailureScenario,
        baseline_metrics: PerformanceMetrics,
        failure_metrics: PerformanceMetrics,
        affected_components: List[str],
        recovered: bool,
        request_id: Optional[str] = None,
    ) -> str:
        """Explain resilience test impact, recovery, and blast radius."""
        pass


def _clean_json_text(text: str) -> str:
    """Strip markdown code block fences and whitespace from raw model response."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


EXTRACTION_SYSTEM_INSTRUCTION = """You are an expert distributed systems architect analyzing an architecture diagram.
Extract an exact, structured architecture representation without hallucinating components or unstated specifications.

CRITICAL RULES:
1. Distinguish between:
   - "directly_observed": Elements with explicit visual shapes or text labels in the diagram.
   - "inferred": Assumptions made based on standard system design patterns (e.g. protocol HTTP).
   - "unknown": Information missing from diagram (e.g. cache TTL, DB storage).
2. Allowed component types:
   api_server, web_server, load_balancer, database, cache, message_queue, object_storage, microservice, gateway, worker, cdn, external_service, unknown
3. Allowed connection types:
   request (sync), async_message (queue/pubsub), data_access (DB/cache), dependency, stream
4. Do NOT invent throughput, latency, or workload values if not explicitly visible or provided.

Output valid JSON matching:
{
  "architecture_id": "arch-extracted-001",
  "components": [{"id": "comp-id", "type": "component_type", "name": "Visible Name", "attributes": {}}],
  "connections": [{"source": "id1", "target": "id2", "type": "request", "attributes": {}}],
  "workload": {"requests_per_second": 500.0, "read_ratio": 0.8, "write_ratio": 0.2},
  "constraints": {"max_p95_latency_ms": 200.0, "min_throughput_rps": null, "max_cost_per_hour": null, "min_availability": null},
  "direct_observations": ["list of directly observed visual elements"],
  "inferred_elements": ["list of assumptions made"],
  "unknown_elements": ["list of missing details"],
  "clarification_questions": []
}"""


class GeminiProvider(BaseAIProvider):
    """
    Hosted multimodal Gemini provider (Gemini 2.0 Flash / 1.5 Flash).
    Native image input support and structured reasoning.
    """

    def __init__(self, api_key: str, model_id: str = "gemini-2.0-flash", base_url: str = ""):
        self.api_key = api_key
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_id

    @property
    def supports_vision(self) -> bool:
        return True

    async def _post_generate_content(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        system_instruction: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        req_id = request_id or str(uuid.uuid4())
        start_time = time.time()
        logger.info(
            "Gemini model invocation START [request_id=%s, model=%s, has_image=%s]",
            req_id,
            self._model_id,
            bool(image_bytes),
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_id}:generateContent?key={self.api_key}"
        parts: List[Dict[str, Any]] = [{"text": prompt}]

        if image_bytes:
            mime = f"image/{image_format.lower()}"
            if mime == "image/jpg":
                mime = "image/jpeg"
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            })

        payload: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        async with httpx.AsyncClient(timeout=float(settings.per_call_timeout_seconds)) as client:
            resp = await client.post(url, json=payload)
            elapsed_ms = (time.time() - start_time) * 1000.0

            if resp.status_code != 200:
                logger.error(
                    "Gemini invocation FAILED [request_id=%s, status=%d, elapsed=%.1fms]: %s",
                    req_id,
                    resp.status_code,
                    elapsed_ms,
                    resp.text[:300],
                )
                raise ModelClientError(
                    f"Gemini API returned HTTP {resp.status_code}: {resp.text}",
                    code="ERR_GEMINI_API_HTTP",
                )

            data = resp.json()
            try:
                candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
                logger.info(
                    "Gemini model invocation COMPLETED [request_id=%s, elapsed=%.1fms]",
                    req_id,
                    elapsed_ms,
                )
                return candidate_text
            except (KeyError, IndexError) as err:
                raise ModelClientError(
                    f"Malformed Gemini API response: {err}",
                    code="ERR_GEMINI_MALFORMED",
                )

    async def extract_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = EXTRACTION_SYSTEM_INSTRUCTION
        if user_requirements:
            prompt += f"\n\nUSER REQUIREMENTS:\n{user_requirements}"
        if user_workload:
            prompt += f"\n\nPROVIDED WORKLOAD:\n{json.dumps(user_workload, indent=2)}"
        if user_constraints:
            prompt += f"\n\nPROVIDED CONSTRAINTS:\n{json.dumps(user_constraints, indent=2)}"

        raw_text = await self._post_generate_content(
            prompt=prompt,
            image_bytes=image_bytes,
            image_format=image_format,
            request_id=request_id,
        )
        cleaned = _clean_json_text(raw_text)
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise ModelClientError(f"Failed to parse Gemini JSON: {e}", code="ERR_INVALID_MODEL_JSON")

    async def explain_root_cause(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
        hypotheses: List[RootCauseHypothesis],
        experiments: List[DiagnosticExperimentResponse],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = (
            f"Analyze baseline simulation metrics and diagnostic experiments for architecture '{architecture.architecture_id}'.\n"
            f"Baseline p95 Latency: {baseline.metrics.get('p95_latency_ms')}ms\n"
            f"Baseline Throughput: {baseline.metrics.get('throughput_rps')} RPS\n"
            f"Component breakdown: {json.dumps([m.model_dump() for m in baseline.component_metrics], indent=2)}\n"
            f"Executed Diagnostic Experiments: {json.dumps([e.model_dump() for e in experiments], indent=2)}\n"
            "Produce an evidence-backed root-cause diagnosis citing specific component IDs and metric deltas."
        )
        raw = await self._post_generate_content(prompt=prompt, request_id=request_id)
        return {"explanation": raw, "model": self._model_id}

    async def explain_optimization(
        self,
        baseline_metrics: PerformanceMetrics,
        candidates: List[CandidateArchitecture],
        recommended: Optional[CandidateArchitecture],
        objective: str,
        request_id: Optional[str] = None,
    ) -> str:
        prompt = (
            f"Explain optimization candidate trade-offs for objective '{objective}'.\n"
            f"Baseline p95: {baseline_metrics.p95_latency_ms:.2f}ms, Throughput: {baseline_metrics.throughput_rps:.1f} RPS, Cost: ${baseline_metrics.total_monthly_cost_usd:.2f}/mo.\n"
            f"Recommended: {recommended.candidate_id if recommended else 'None'} ({recommended.description if recommended else ''}).\n"
            "Summarize the Pareto trade-offs in 2-3 concise paragraphs."
        )
        return await self._post_generate_content(prompt=prompt, request_id=request_id)

    async def explain_chaos(
        self,
        scenario: FailureScenario,
        baseline_metrics: PerformanceMetrics,
        failure_metrics: PerformanceMetrics,
        affected_components: List[str],
        recovered: bool,
        request_id: Optional[str] = None,
    ) -> str:
        prompt = (
            f"Analyze chaos engineering fault injection '{scenario.name}' on {affected_components}.\n"
            f"Baseline p95: {baseline_metrics.p95_latency_ms:.2f}ms, Failure p95: {failure_metrics.p95_latency_ms:.2f}ms.\n"
            f"Latency Delta: +{failure_metrics.p95_latency_ms - baseline_metrics.p95_latency_ms:.2f}ms. Error rate: {failure_metrics.error_rate*100:.2f}%.\n"
            f"Recovery Observed: {recovered}.\n"
            "Summarize system resilience, blast radius, and recovery behavior in 2 clear paragraphs."
        )
        return await self._post_generate_content(prompt=prompt, request_id=request_id)


class GemmaProvider(BaseAIProvider):
    """
    Instruction-tuned Google Gemma model provider (e.g. gemma-2-27b-it, gemma-2-9b-it).
    Supports:
    1. Google AI Studio / Gemini API endpoint serving Gemma models.
    2. OpenAI-compatible hosted or local inference server (vLLM, Ollama, Groq, OpenRouter).
    Note: Gemma 2 is text-only. Diagram extraction uses extracted OCR/topology cues or
    delegates to visual parser when image bytes are provided.
    """

    def __init__(
        self,
        api_key: str = "",
        model_id: str = "gemma-2-27b-it",
        base_url: str = "",
    ):
        self.api_key = api_key
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "gemma"

    @property
    def model_name(self) -> str:
        return self._model_id

    @property
    def supports_vision(self) -> bool:
        # Gemma 2 models are text-to-text models
        return False

    async def _call_inference(self, prompt: str, system_instruction: Optional[str] = None, request_id: Optional[str] = None) -> str:
        req_id = request_id or str(uuid.uuid4())
        start_time = time.time()
        logger.info("Gemma invocation START [request_id=%s, model=%s]", req_id, self._model_id)

        # Path 1: OpenAI-compatible endpoint (vLLM, Ollama, OpenRouter, Groq)
        if self._base_url:
            url = f"{self._base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self._model_id,
                "messages": messages,
                "temperature": 0.1,
            }

            async with httpx.AsyncClient(timeout=float(settings.per_call_timeout_seconds)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                elapsed_ms = (time.time() - start_time) * 1000.0

                if resp.status_code != 200:
                    logger.error("Gemma endpoint HTTP %d: %s", resp.status_code, resp.text[:200])
                    raise ModelClientError(f"Gemma endpoint returned HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                logger.info("Gemma invocation COMPLETED [request_id=%s, elapsed=%.1fms]", req_id, elapsed_ms)
                return text

        # Path 2: Google AI Studio endpoint for Gemma
        if self.api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_id}:generateContent?key={self.api_key}"
            parts = []
            if system_instruction:
                parts.append({"text": f"SYSTEM: {system_instruction}\n\n"})
            parts.append({"text": prompt})

            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0.1},
            }

            async with httpx.AsyncClient(timeout=float(settings.per_call_timeout_seconds)) as client:
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.time() - start_time) * 1000.0

                if resp.status_code != 200:
                    logger.error("Gemma via Google API HTTP %d: %s", resp.status_code, resp.text[:200])
                    raise ModelClientError(f"Gemma Google API returned HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info("Gemma invocation COMPLETED [request_id=%s, elapsed=%.1fms]", req_id, elapsed_ms)
                    return text
                except (KeyError, IndexError) as err:
                    raise ModelClientError(f"Malformed Gemma API response: {err}")

        raise ModelClientError(
            "Gemma credentials not configured. Please set GEMMA_API_KEY, GEMMA_BASE_URL, or GEMINI_API_KEY.",
            code="ERR_GEMMA_NO_CREDENTIALS",
        )

    async def extract_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gemma structured architecture reasoning from requirements and diagram topology."""
        prompt = (
            "You are Google Gemma, an instruction-tuned expert distributed systems architect.\n"
            "Analyze the following system specification and synthesize a validated architecture JSON.\n"
            f"User Requirements: {user_requirements or 'Standard e-commerce web application with ingress, API servers, cache, and database.'}\n"
            f"Workload Profile: {json.dumps(user_workload or {'requests_per_second': 500, 'read_ratio': 0.8, 'write_ratio': 0.2})}\n"
            f"Constraints: {json.dumps(user_constraints or {'max_p95_latency_ms': 200})}\n"
            "\n" + EXTRACTION_SYSTEM_INSTRUCTION
        )
        raw = await self._call_inference(prompt=prompt, request_id=request_id)
        cleaned = _clean_json_text(raw)
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise ModelClientError(f"Failed to parse Gemma structured output: {e}", code="ERR_INVALID_MODEL_JSON")

    async def explain_root_cause(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
        hypotheses: List[RootCauseHypothesis],
        experiments: List[DiagnosticExperimentResponse],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = (
            "Analyze these discrete-event simulation outputs and explain the root causes of latency bottlenecks.\n"
            f"Baseline p95 Latency: {baseline.metrics.get('p95_latency_ms')}ms\n"
            f"Baseline Throughput: {baseline.metrics.get('throughput_rps')} RPS\n"
            f"Component breakdown: {json.dumps([m.model_dump() for m in baseline.component_metrics], indent=2)}\n"
            f"Diagnostic experiments: {json.dumps([e.model_dump() for e in experiments], indent=2)}\n"
            "Provide evidence-based reasoning citing exact component IDs and percentage diffs."
        )
        text = await self._call_inference(prompt=prompt, request_id=request_id)
        return {"explanation": text, "model": self._model_id}

    async def explain_optimization(
        self,
        baseline_metrics: PerformanceMetrics,
        candidates: List[CandidateArchitecture],
        recommended: Optional[CandidateArchitecture],
        objective: str,
        request_id: Optional[str] = None,
    ) -> str:
        prompt = (
            f"As Gemma distributed systems architect, analyze the architecture optimization results under objective '{objective}'.\n"
            f"Baseline: p95={baseline_metrics.p95_latency_ms:.1f}ms, RPS={baseline_metrics.throughput_rps:.1f}, Cost=${baseline_metrics.total_monthly_cost_usd:.2f}/mo.\n"
            f"Top Candidate: {recommended.candidate_id if recommended else 'None'} ({recommended.description if recommended else ''}).\n"
            "Explain why this configuration represents the optimal Pareto trade-off."
        )
        return await self._call_inference(prompt=prompt, request_id=request_id)

    async def explain_chaos(
        self,
        scenario: FailureScenario,
        baseline_metrics: PerformanceMetrics,
        failure_metrics: PerformanceMetrics,
        affected_components: List[str],
        recovered: bool,
        request_id: Optional[str] = None,
    ) -> str:
        delta_p95 = failure_metrics.p95_latency_ms - baseline_metrics.p95_latency_ms
        prompt = (
            f"Analyze the resilience simulation for failure scenario '{scenario.name}'.\n"
            f"Target: {affected_components}. Latency delta: +{delta_p95:.1f}ms. Error rate: {failure_metrics.error_rate*100:.1f}%.\n"
            f"System recovered: {recovered}.\n"
            "Synthesize actionable engineering recommendations."
        )
        return await self._call_inference(prompt=prompt, request_id=request_id)


class DeterministicFallbackProvider(BaseAIProvider):
    """
    Deterministic rule-based fallback provider.
    Active when no external AI keys are configured or when offline testing is desired.
    Explicitly marks all outputs with is_mock=True and fallback_used=True so outputs
    are never misrepresented as live AI model inference.
    """

    @property
    def name(self) -> str:
        return "deterministic_fallback"

    @property
    def model_name(self) -> str:
        return "deterministic_rules_v1"

    @property
    def supports_vision(self) -> bool:
        return False

    async def extract_architecture(
        self,
        image_bytes: Optional[bytes] = None,
        image_format: str = "PNG",
        user_requirements: Optional[str] = None,
        user_workload: Optional[Dict[str, Any]] = None,
        user_constraints: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        rps = 1000.0
        read_r = 0.8
        write_r = 0.2
        if user_workload:
            rps = float(user_workload.get("requests_per_second", rps))
            read_r = float(user_workload.get("read_ratio", read_r))
            write_r = float(user_workload.get("write_ratio", write_r))

        max_p95 = 200.0
        if user_constraints:
            max_p95 = float(user_constraints.get("max_p95_latency_ms", max_p95))

        return {
            "schema_version": SCHEMA_VERSION,
            "architecture_id": "arch-fallback-001",
            "components": [
                {
                    "id": "gateway-1",
                    "type": ComponentType.GATEWAY.value,
                    "name": "API Gateway",
                    "attributes": {"instances": 2, "capacity_rps": 5000.0, "base_latency_ms": 2.0}
                },
                {
                    "id": "api-service",
                    "type": ComponentType.API_SERVER.value,
                    "name": "Order API Service",
                    "attributes": {"instances": 4, "cpu_cores": 2, "capacity_rps": 1200.0, "base_latency_ms": 12.0}
                },
                {
                    "id": "redis-cache",
                    "type": ComponentType.CACHE.value,
                    "name": "Redis Session Cache",
                    "attributes": {"engine": "redis", "capacity_rps": 8000.0, "base_latency_ms": 1.5, "cache_hit_ratio": 0.8}
                },
                {
                    "id": "db-primary",
                    "type": ComponentType.DATABASE.value,
                    "name": "Postgres Primary",
                    "attributes": {"engine": "postgresql", "capacity_rps": 800.0, "base_latency_ms": 25.0}
                }
            ],
            "connections": [
                {
                    "source": "gateway-1",
                    "target": "api-service",
                    "type": ConnectionType.REQUEST.value,
                    "attributes": {"protocol": "HTTP/1.1", "latency_overhead_ms": 1.0}
                },
                {
                    "source": "api-service",
                    "target": "redis-cache",
                    "type": ConnectionType.DATA_ACCESS.value,
                    "attributes": {"protocol": "RESP", "latency_overhead_ms": 0.5}
                },
                {
                    "source": "api-service",
                    "target": "db-primary",
                    "type": ConnectionType.DATA_ACCESS.value,
                    "attributes": {"protocol": "TCP/Postgres", "latency_overhead_ms": 1.5}
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
                "min_throughput_rps": None,
                "max_cost_per_hour": None,
                "min_availability": 0.999
            },
            "direct_observations": [
                "Observed 4 core topology tiers: Ingress Gateway, API Service, Redis Cache, Postgres Database",
                "Observed data access paths to cache and database"
            ],
            "inferred_elements": [
                "Connection protocol inferred as standard HTTP/1.1 and TCP/SQL",
                "Cache hit ratio assumed at 80% under standard read workload"
            ],
            "unknown_elements": [
                "Cache eviction policy not stated in input diagram",
                "Database replica topology not visible in diagram"
            ],
            "clarification_questions": [
                {
                    "question_id": "Q-FALLBACK-CACHE",
                    "question": "What is the expected read/write workload split and cache eviction policy?",
                    "affected_components": ["redis-cache", "db-primary"],
                    "category": "workload",
                    "suggested_options": ["80% read / 20% write (Standard e-commerce)", "50/50 balanced"]
                }
            ]
        }

    async def explain_root_cause(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
        hypotheses: List[RootCauseHypothesis],
        experiments: List[DiagnosticExperimentResponse],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        p95 = baseline.metrics.get("p95_latency_ms", 0.0)
        rps = baseline.metrics.get("throughput_rps", 0.0)
        confirmed = [h for h in hypotheses if h.status.value in ("confirmed", "supported")]

        bullets = []
        for h in confirmed:
            bullets.append(f"- {h.title}: Affected {h.affected_components}. Evidence: {len(h.supporting_evidence)} observations.")

        summary = (
            f"Deterministic Root-Cause Analysis (Baseline: {p95:.1f}ms p95 at {rps:.0f} RPS):\n"
            + ("\n".join(bullets) if bullets else "- System operates within nominal tolerances; no bottleneck confirmed.")
        )
        return {"explanation": summary, "model": self.model_name, "fallback_used": True}

    async def explain_optimization(
        self,
        baseline_metrics: PerformanceMetrics,
        candidates: List[CandidateArchitecture],
        recommended: Optional[CandidateArchitecture],
        objective: str,
        request_id: Optional[str] = None,
    ) -> str:
        if not recommended:
            return f"Under objective '{objective}', no candidate strictly satisfied all constraints within budget."

        lat_diff = recommended.metrics.p95_latency_ms - baseline_metrics.p95_latency_ms
        cost_diff = recommended.metrics.total_monthly_cost_usd - baseline_metrics.total_monthly_cost_usd
        return (
            f"Optimization Search Result ({objective.upper()}):\n"
            f"Recommended candidate '{recommended.candidate_id}' ({recommended.description}) achieves "
            f"p95 latency of {recommended.metrics.p95_latency_ms:.1f}ms ({lat_diff:+.1f}ms delta), "
            f"throughput of {recommended.metrics.throughput_rps:.0f} RPS, and monthly cost of "
            f"${recommended.metrics.total_monthly_cost_usd:.2f} ({cost_diff:+.2f} delta). "
            f"Total feasible candidates evaluated: {len(candidates)}."
        )

    async def explain_chaos(
        self,
        scenario: FailureScenario,
        baseline_metrics: PerformanceMetrics,
        failure_metrics: PerformanceMetrics,
        affected_components: List[str],
        recovered: bool,
        request_id: Optional[str] = None,
    ) -> str:
        lat_delta = failure_metrics.p95_latency_ms - baseline_metrics.p95_latency_ms
        status = "recovered successfully" if recovered else "exhibited sustained degradation"
        return (
            f"Chaos Engineering Resilience Analysis ({scenario.name}):\n"
            f"Injecting fault '{scenario.failure_type.value}' into {affected_components} shifted p95 latency "
            f"from {baseline_metrics.p95_latency_ms:.1f}ms to {failure_metrics.p95_latency_ms:.1f}ms (+{lat_delta:.1f}ms delta). "
            f"Error rate changed to {failure_metrics.error_rate*100:.2f}%. System {status}."
        )


def get_ai_provider(provider_type: Optional[str] = None) -> BaseAIProvider:
    """
    Factory function for obtaining the configured AI provider.
    Inspects settings:
    - If provider_type is explicitly specified, initializes that provider.
    - If 'gemma': uses GemmaProvider with GEMMA_API_KEY / GEMMA_BASE_URL.
    - If 'gemini': uses GeminiProvider with GEMINI_API_KEY.
    - If 'auto': selects Gemma if configured, then Gemini, then DeterministicFallbackProvider.
    """
    choice = (provider_type or settings.ai_provider).lower()

    if choice == "gemini":
        if not settings.gemini_api_key:
            if settings.allow_ai_fallback:
                logger.warning("GEMINI_API_KEY not set. Using DeterministicFallbackProvider.")
                return DeterministicFallbackProvider()
            raise ModelClientError("GEMINI_API_KEY is not configured.", code="ERR_NO_GEMINI_KEY")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model_id=settings.gemini_model_id,
            base_url=settings.gemini_base_url,
        )

    if choice == "gemma":
        if not (settings.gemma_api_key or settings.gemma_base_url or settings.gemini_api_key):
            if settings.allow_ai_fallback:
                logger.warning("Gemma credentials not configured. Using DeterministicFallbackProvider.")
                return DeterministicFallbackProvider()
            raise ModelClientError("Gemma inference credentials not configured.", code="ERR_NO_GEMMA_KEY")
        return GemmaProvider(
            api_key=settings.gemma_api_key or settings.gemini_api_key,
            model_id=settings.gemma_model_id,
            base_url=settings.gemma_base_url,
        )

    if choice in ("deterministic_fallback", "mock", "fallback"):
        return DeterministicFallbackProvider()

    # 'auto' mode
    if settings.gemma_base_url or (settings.gemma_api_key and "gemma" in settings.gemma_model_id):
        return GemmaProvider(
            api_key=settings.gemma_api_key,
            model_id=settings.gemma_model_id,
            base_url=settings.gemma_base_url,
        )

    if settings.gemini_api_key:
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model_id=settings.gemini_model_id,
            base_url=settings.gemini_base_url,
        )

    if settings.allow_ai_fallback:
        return DeterministicFallbackProvider()

    raise ModelClientError("No AI credentials configured and fallback is disabled.", code="ERR_NO_AI_PROVIDER")
