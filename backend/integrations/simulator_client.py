"""
ArchPilot AI - Simulator Client Adapter (Member 2 Engine Integration)
Member 1: Architecture Understanding & Root-Cause Investigation

Defines the integration contract and client adapter for Member 2's simulation engine.
Includes a deterministic mock simulator when the real engine is not yet connected.
Enforces strict labels on mock data, handles timeouts and bounded retries,
and validates all incoming and outgoing schemas.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

from backend.config import settings
from backend.shared.schemas import (
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    ComponentMetric,
    ComponentType,
    DiagnosticExperimentRequest,
    DiagnosticExperimentResponse,
    MetricDiff,
    SimulationStatus,
    SupportedDiagnosticExperiment,
)

logger = logging.getLogger("archpilot.simulator_client")


class SimulatorClientError(Exception):
    def __init__(self, message: str, code: str = "ERR_SIMULATOR"):
        super().__init__(message)
        self.message = message
        self.code = code


class SimulatorTimeoutError(SimulatorClientError):
    def __init__(self, message: str = "Simulator request timed out"):
        super().__init__(message, code="ERR_SIMULATOR_TIMEOUT")


class SimulatorUnavailableError(SimulatorClientError):
    def __init__(self, message: str = "Simulator service unavailable"):
        super().__init__(message, code="ERR_SIMULATOR_UNAVAILABLE")


class SimulatorClient:
    """
    Adapter for Member 2 simulation engine.
    Dispatches to real HTTP API if configured, otherwise uses deterministic mock.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        use_mock: Optional[bool] = None,
    ):
        self.base_url = (base_url or settings.simulator_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.simulator_timeout_seconds
        # If no base_url is configured, automatically use mock
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            self.use_mock = settings.use_mock_simulator or not bool(self.base_url)

    async def run_baseline(
        self,
        request: BaselineSimulationRequest,
    ) -> BaselineSimulationResponse:
        """
        Executes baseline simulation for the given architecture.
        """
        if self.use_mock:
            return self._run_mock_baseline(request)

        return await self._call_real_baseline(request)

    async def run_diagnostic(
        self,
        request: DiagnosticExperimentRequest,
        baseline: BaselineSimulationResponse,
    ) -> DiagnosticExperimentResponse:
        """
        Executes a targeted diagnostic experiment and calculates diffs from baseline.
        """
        if self.use_mock:
            return self._run_mock_diagnostic(request, baseline)

        return await self._call_real_diagnostic(request, baseline)

    async def _call_real_baseline(
        self,
        request: BaselineSimulationRequest,
    ) -> BaselineSimulationResponse:
        url = f"{self.base_url}/api/v1/simulate/baseline"
        payload = request.model_dump(mode="json")

        last_err: Optional[Exception] = None
        for attempt in range(1, settings.max_retries + 2):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        data["is_mock"] = False
                        data["source"] = "member2_simulator"
                        return BaselineSimulationResponse(**data)
                    elif resp.status_code in (502, 503, 504):
                        raise SimulatorUnavailableError(f"Simulator service error HTTP {resp.status_code}: {resp.text}")
                    else:
                        raise SimulatorClientError(
                            f"Simulator returned unexpected HTTP {resp.status_code}: {resp.text}",
                            code="ERR_SIMULATOR_HTTP",
                        )
            except httpx.TimeoutException as e:
                last_err = SimulatorTimeoutError(f"Simulator call timed out after {self.timeout_seconds}s: {e}")
            except httpx.ConnectError as e:
                last_err = SimulatorUnavailableError(f"Cannot connect to simulator at {url}: {e}")
            except SimulatorClientError as e:
                last_err = e
            except Exception as e:
                last_err = SimulatorClientError(f"Simulator response validation failed: {e}", code="ERR_SIMULATOR_PAYLOAD")

            if attempt <= settings.max_retries:
                await asyncio.sleep(0.5 * attempt)

        raise last_err or SimulatorClientError("Baseline simulation failed after retries")

    async def _call_real_diagnostic(
        self,
        request: DiagnosticExperimentRequest,
        baseline: BaselineSimulationResponse,
    ) -> DiagnosticExperimentResponse:
        url = f"{self.base_url}/api/v1/simulate/diagnostic"
        payload = request.model_dump(mode="json")

        last_err: Optional[Exception] = None
        for attempt in range(1, settings.max_retries + 2):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        data["is_mock"] = False
                        data["source"] = "member2_simulator"
                        return DiagnosticExperimentResponse(**data)
                    elif resp.status_code in (502, 503, 504):
                        raise SimulatorUnavailableError(f"Simulator service error HTTP {resp.status_code}: {resp.text}")
                    else:
                        raise SimulatorClientError(f"Simulator returned HTTP {resp.status_code}: {resp.text}")
            except httpx.TimeoutException as e:
                last_err = SimulatorTimeoutError(f"Diagnostic simulation timed out: {e}")
            except httpx.ConnectError as e:
                last_err = SimulatorUnavailableError(f"Cannot connect to simulator at {url}: {e}")
            except SimulatorClientError as e:
                last_err = e
            except Exception as e:
                last_err = SimulatorClientError(f"Diagnostic response validation failed: {e}")

            if attempt <= settings.max_retries:
                await asyncio.sleep(0.5 * attempt)

        raise last_err or SimulatorClientError("Diagnostic simulation failed after retries")

    # =========================================================================
    # Deterministic Mock Simulator
    # =========================================================================

    def _run_mock_baseline(
        self,
        request: BaselineSimulationRequest,
    ) -> BaselineSimulationResponse:
        """
        Deterministic, realistic baseline calculation clearly marked as mock data.
        """
        workload = request.architecture.workload
        components = request.architecture.components
        rps = workload.requests_per_second
        write_ratio = workload.write_ratio

        # Find primary DB and API server components
        db_comp = next((c for c in components if c.type == ComponentType.DATABASE), None)
        api_comp = next((c for c in components if c.type in (ComponentType.API_SERVER, ComponentType.MICROSERVICE)), None)
        cache_comp = next((c for c in components if c.type == ComponentType.CACHE), None)

        # Baseline calculations:
        # Base latency: 30ms network/gateway + 25ms app compute
        # If cache exists: 70% cache hit reduces DB read load
        cache_hit_ratio = 0.70 if cache_comp else 0.0
        effective_db_rps = rps * (write_ratio + (1.0 - write_ratio) * (1.0 - cache_hit_ratio))

        # DB CPU formula based on capacity (assume standard 500 RPS per DB core)
        db_cores = float(db_comp.attributes.get("cpu_cores", 2)) if db_comp else 2.0
        db_capacity = db_cores * 400.0
        db_utilization_pct = min(100.0, max(15.0, (effective_db_rps / db_capacity) * 100.0))

        # Non-linear queuing latency when DB CPU > 70%
        queue_latency_ms = 0.0
        if db_utilization_pct > 70.0:
            queue_latency_ms = ((db_utilization_pct - 70.0) ** 1.8) * 1.5

        db_latency_p95_ms = 40.0 + queue_latency_ms
        app_latency_p95_ms = 25.0 + (queue_latency_ms * 0.2)
        system_p95_latency_ms = round(30.0 + app_latency_p95_ms + db_latency_p95_ms, 2)
        throughput_rps = round(min(rps, rps * (100.0 / max(100.0, db_utilization_pct))), 1)

        # Cost estimation: ~$0.15/hr per API instance, ~$0.45/hr per DB instance, ~$0.08/hr per Cache
        cost_per_hour = round(len(components) * 0.25, 2)
        availability = 0.999 if db_utilization_pct < 90.0 else 0.985

        # Component metrics
        comp_metrics: List[ComponentMetric] = []
        for comp in components:
            if comp.type == ComponentType.DATABASE:
                comp_metrics.append(
                    ComponentMetric(
                        component_id=comp.id,
                        cpu_utilization_pct=round(db_utilization_pct, 1),
                        memory_utilization_pct=65.0,
                        latency_p95_ms=round(db_latency_p95_ms, 2),
                        throughput_rps=round(effective_db_rps, 1),
                        error_rate_pct=1.5 if db_utilization_pct > 90.0 else 0.0,
                    )
                )
            elif comp.type in (ComponentType.API_SERVER, ComponentType.MICROSERVICE):
                api_cpu = min(90.0, max(10.0, (rps / 1500.0) * 100.0))
                comp_metrics.append(
                    ComponentMetric(
                        component_id=comp.id,
                        cpu_utilization_pct=round(api_cpu, 1),
                        memory_utilization_pct=50.0,
                        latency_p95_ms=round(app_latency_p95_ms, 2),
                        throughput_rps=round(throughput_rps, 1),
                        error_rate_pct=0.0,
                    )
                )
            elif comp.type == ComponentType.CACHE:
                comp_metrics.append(
                    ComponentMetric(
                        component_id=comp.id,
                        cpu_utilization_pct=25.0,
                        memory_utilization_pct=45.0,
                        latency_p95_ms=3.5,
                        throughput_rps=round(rps * (1.0 - write_ratio), 1),
                        error_rate_pct=0.0,
                    )
                )
            else:
                comp_metrics.append(
                    ComponentMetric(
                        component_id=comp.id,
                        cpu_utilization_pct=20.0,
                        memory_utilization_pct=30.0,
                        latency_p95_ms=10.0,
                        throughput_rps=round(rps, 1),
                        error_rate_pct=0.0,
                    )
                )

        warnings: List[str] = []
        if db_utilization_pct >= 80.0:
            warnings.append(
                f"Database component '{db_comp.id if db_comp else 'database'}' CPU reached {db_utilization_pct:.1f}% under baseline load"
            )
        if system_p95_latency_ms > (request.architecture.constraints.max_p95_latency_ms or 9999.0):
            warnings.append(
                f"Observed p95 latency ({system_p95_latency_ms}ms) violates target constraint ({request.architecture.constraints.max_p95_latency_ms}ms)"
            )

        return BaselineSimulationResponse(
            run_id=request.run_id,
            status=SimulationStatus.COMPLETED,
            source="mock_simulator",
            is_mock=True,
            metrics={
                "p95_latency_ms": system_p95_latency_ms,
                "throughput_rps": throughput_rps,
                "cost_per_hour": cost_per_hour,
                "availability": availability,
            },
            component_metrics=comp_metrics,
            warnings=warnings,
            assumptions=[
                "Mock simulation: database queuing model uses M/M/c approximation.",
                "Network latency between local VPC components assumed to be 1.5ms.",
            ],
            simulator_version="mock-v1.0.0",
        )

    def _run_mock_diagnostic(
        self,
        request: DiagnosticExperimentRequest,
        baseline: BaselineSimulationResponse,
    ) -> DiagnosticExperimentResponse:
        """
        Deterministic, realistic response to diagnostic parameters.
        Generates genuine MetricDiffs against baseline.
        """
        baseline_p95 = baseline.metrics.get("p95_latency_ms") or 100.0
        baseline_rps = baseline.metrics.get("throughput_rps") or 1000.0
        baseline_cost = baseline.metrics.get("cost_per_hour") or 1.0
        baseline_avail = baseline.metrics.get("availability") or 0.999

        diffs: List[MetricDiff] = []
        warnings: List[str] = []
        diag_metrics: Dict[str, Optional[float]] = {}
        diag_comp_metrics: List[ComponentMetric] = []

        exp_type = request.experiment_type
        params = request.parameters_to_change

        def safe_pct(diff_val: float, base_val: Optional[float]) -> Optional[float]:
            if base_val and base_val != 0.0:
                return round((diff_val / base_val) * 100.0, 1)
            return None

        if exp_type == SupportedDiagnosticExperiment.INCREASE_WORKLOAD:
            multiplier = float(params.get("multiplier", 1.5))
            new_p95 = round(baseline_p95 * (multiplier ** 1.6), 2)
            new_rps = round(baseline_rps * min(multiplier, 1.2), 1)
            new_avail = round(max(0.95, baseline_avail - 0.03), 3)

            diag_metrics = {
                "p95_latency_ms": new_p95,
                "throughput_rps": new_rps,
                "cost_per_hour": baseline_cost,
                "availability": new_avail,
            }
            diffs.append(
                MetricDiff(
                    metric_name="p95_latency_ms",
                    baseline_value=baseline_p95,
                    diagnostic_value=new_p95,
                    diff_value=round(new_p95 - baseline_p95, 2),
                    diff_pct=safe_pct(new_p95 - baseline_p95, baseline_p95),
                    unit="ms",
                    interpretation=f"Workload increase of {multiplier}x caused non-linear latency spike of +{new_p95 - baseline_p95:.1f}ms, indicating queue saturation.",
                )
            )
            diffs.append(
                MetricDiff(
                    metric_name="throughput_rps",
                    baseline_value=baseline_rps,
                    diagnostic_value=new_rps,
                    diff_value=round(new_rps - baseline_rps, 1),
                    diff_pct=safe_pct(new_rps - baseline_rps, baseline_rps),
                    unit="rps",
                    interpretation="Throughput flattened relative to offered load, confirming bottleneck.",
                )
            )

        elif exp_type == SupportedDiagnosticExperiment.SIMULATE_DB_LATENCY:
            added_latency_ms = float(params.get("db_latency_overhead_ms", 50.0))
            new_p95 = round(baseline_p95 + added_latency_ms * 1.2, 2)
            diag_metrics = {
                "p95_latency_ms": new_p95,
                "throughput_rps": baseline_rps,
                "cost_per_hour": baseline_cost,
                "availability": baseline_avail,
            }
            diffs.append(
                MetricDiff(
                    metric_name="p95_latency_ms",
                    baseline_value=baseline_p95,
                    diagnostic_value=new_p95,
                    diff_value=round(new_p95 - baseline_p95, 2),
                    diff_pct=safe_pct(new_p95 - baseline_p95, baseline_p95),
                    unit="ms",
                    interpretation=f"Injected {added_latency_ms}ms DB overhead propagated directly to end-to-end p95 latency.",
                )
            )

        elif exp_type == SupportedDiagnosticExperiment.VARY_READ_WRITE_MIX:
            new_write_ratio = float(params.get("write_ratio", 0.5))
            # Higher write ratio increases contention on DB
            write_delta = new_write_ratio - 0.2
            latency_factor = 1.0 + (write_delta * 1.5)
            new_p95 = round(baseline_p95 * latency_factor, 2)
            diag_metrics = {
                "p95_latency_ms": new_p95,
                "throughput_rps": baseline_rps,
                "cost_per_hour": baseline_cost,
                "availability": baseline_avail,
            }
            diffs.append(
                MetricDiff(
                    metric_name="p95_latency_ms",
                    baseline_value=baseline_p95,
                    diagnostic_value=new_p95,
                    diff_value=round(new_p95 - baseline_p95, 2),
                    diff_pct=safe_pct(new_p95 - baseline_p95, baseline_p95),
                    unit="ms",
                    interpretation=f"Increasing write ratio to {new_write_ratio*100:.0f}% changed p95 latency by {new_p95 - baseline_p95:+.1f}ms.",
                )
            )

        elif exp_type == SupportedDiagnosticExperiment.SCALE_COMPONENT:
            replicas = int(params.get("replicas", 2))
            new_p95 = round(max(35.0, baseline_p95 * (1.0 / (replicas ** 0.6))), 2)
            new_cost = round(baseline_cost * 1.4, 2)
            diag_metrics = {
                "p95_latency_ms": new_p95,
                "throughput_rps": baseline_rps,
                "cost_per_hour": new_cost,
                "availability": 0.9995,
            }
            diffs.append(
                MetricDiff(
                    metric_name="p95_latency_ms",
                    baseline_value=baseline_p95,
                    diagnostic_value=new_p95,
                    diff_value=round(new_p95 - baseline_p95, 2),
                    diff_pct=safe_pct(new_p95 - baseline_p95, baseline_p95),
                    unit="ms",
                    interpretation=f"Scaling component to {replicas} replicas relieved bottleneck and reduced p95 latency by {baseline_p95 - new_p95:.1f}ms.",
                )
            )

        elif exp_type == SupportedDiagnosticExperiment.TOGGLE_CACHE:
            enabled = bool(params.get("enabled", False))
            if not enabled:
                new_p95 = round(baseline_p95 * 2.2, 2)
                diag_metrics = {
                    "p95_latency_ms": new_p95,
                    "throughput_rps": round(baseline_rps * 0.7, 1),
                    "cost_per_hour": baseline_cost,
                    "availability": 0.975,
                }
                diffs.append(
                    MetricDiff(
                        metric_name="p95_latency_ms",
                        baseline_value=baseline_p95,
                        diagnostic_value=new_p95,
                        diff_value=round(new_p95 - baseline_p95, 2),
                        diff_pct=safe_pct(new_p95 - baseline_p95, baseline_p95),
                        unit="ms",
                        interpretation="Bypassing cache forced 100% of read traffic onto the primary DB, spiking latency and lowering throughput.",
                    )
                )
            else:
                diag_metrics = dict(baseline.metrics)

        else:
            diag_metrics = dict(baseline.metrics)

        # Clone baseline component metrics with adjusted values
        for cm in baseline.component_metrics:
            if cm.component_id in request.target_components:
                # Target component affected
                diag_comp_metrics.append(
                    ComponentMetric(
                        component_id=cm.component_id,
                        cpu_utilization_pct=min(100.0, (cm.cpu_utilization_pct or 50.0) * 1.3),
                        memory_utilization_pct=cm.memory_utilization_pct,
                        latency_p95_ms=diag_metrics.get("p95_latency_ms"),
                        throughput_rps=cm.throughput_rps,
                        error_rate_pct=cm.error_rate_pct,
                    )
                )
            else:
                diag_comp_metrics.append(cm)

        return DiagnosticExperimentResponse(
            experiment_id=request.experiment_id,
            baseline_run_id=request.baseline_run_id,
            status=SimulationStatus.COMPLETED,
            source="mock_simulator",
            is_mock=True,
            metrics=diag_metrics,
            component_metrics=diag_comp_metrics,
            diff_from_baseline=diffs,
            warnings=warnings,
            simulator_version="mock-v1.0.0",
        )
