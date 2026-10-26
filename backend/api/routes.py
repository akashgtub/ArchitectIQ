"""
ArchitectIQ - Unified API Endpoints
Combines:
- Member 1: Architecture Understanding, Image Diagram Extraction, Graph Validation, & Root-Cause Investigation
- Member 2: Simulation Engine, Optimization Search, Resilience Chaos Testing, and Simulator Integration Endpoints
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

# Member 1 Services & Schemas
from backend.ai_agent.architecture_parser import ArchitectureParserService
from backend.ai_agent.gemma_client import ModelClientError
from backend.ai_agent.handoff_builder import HandoffBuilder
from backend.ai_agent.image_validator import ImageValidationError
from backend.ai_agent.root_cause import RootCauseInvestigator
from backend.integrations.simulator_client import (
    SimulatorClient,
    SimulatorClientError,
    SimulatorTimeoutError,
    SimulatorUnavailableError,
)
from backend.shared.adapter import (
    adapt_m1_architecture_to_m2,
    adapt_m2_simulation_to_m1_baseline,
    run_adapted_diagnostic_experiment,
)
from backend.shared.schemas import (
    Architecture,
    ArchitectureAnalyzeResponse,
    ArchitectureValidationResult,
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    DiagnosticExperimentRequest,
    DiagnosticExperimentResponse,
    ErrorResponse,
    InvestigationDetailResponse,
    InvestigationStatus,
    Member1Handoff,
    StartInvestigationRequest,
)

# Member 2 Services & Schemas
from backend.api.service import optimize_architecture, run_simulation, simulate_failure
from backend.simulator.engine import SimulationEngine, SimulationError
from backend.simulator.schemas import (
    ArchitectureGraph,
    Constraints as M2Constraints,
    FailureScenario,
    FailureSimulationResult,
    OptimizationObjective,
    OptimizationResult,
    SimulationResult,
    WorkloadConfig,
)

logger = logging.getLogger("architectiq.api")

router = APIRouter()

# In-memory stores for investigations and baseline simulation runs
_INVESTIGATIONS_DB: Dict[str, Dict[str, Any]] = {}
_BASELINE_STORE: Dict[str, tuple[Architecture, BaselineSimulationResponse]] = {}


def get_architecture_parser() -> ArchitectureParserService:
    return ArchitectureParserService()


def get_simulator_client() -> SimulatorClient:
    return SimulatorClient()


def get_root_cause_investigator(sim_client: SimulatorClient) -> RootCauseInvestigator:
    return RootCauseInvestigator(simulator_client=sim_client)


def get_handoff_builder() -> HandoffBuilder:
    return HandoffBuilder()


# ============================================================================
# Member 2 Request Models (Pydantic v2)
# ============================================================================

class SimulationRunRequest(BaseModel):
    """Payload for running baseline architecture simulation."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph = Field(..., description="Architecture topology graph")
    workload: WorkloadConfig = Field(..., description="Simulation workload profile")
    constraints: Optional[M2Constraints] = Field(None, description="Optional performance and budget constraints")


class OptimizationRunRequest(BaseModel):
    """Payload for architecture optimization search."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph = Field(..., description="Baseline architecture topology graph")
    workload: WorkloadConfig = Field(..., description="Simulation workload profile")
    constraints: Optional[M2Constraints] = Field(None, description="Boundary performance and budget constraints")
    objective: OptimizationObjective = Field(
        default=OptimizationObjective.BALANCED,
        description="Target optimization objective (minimize_latency, minimize_cost, maximize_throughput, balanced)",
    )
    max_candidates: int = Field(default=8, ge=1, le=50, description="Maximum number of candidates to evaluate")


class ChaosRunRequest(BaseModel):
    """Payload for chaos engineering fault injection."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph = Field(..., description="Architecture topology graph")
    workload: WorkloadConfig = Field(..., description="Simulation workload profile")
    scenario: FailureScenario = Field(..., description="Chaos engineering failure scenario")
    constraints: Optional[M2Constraints] = Field(None, description="Optional performance and budget constraints")


# ============================================================================
# Health Check Endpoints
# ============================================================================

@router.get("/health", summary="Health Check", tags=["System"])
@router.get("/api/v1/health", summary="Health Check", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ArchitectIQ - System Architecture Analysis & Simulation Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
    }


# ============================================================================
# Member 2 Core Simulation, Optimization, and Chaos Endpoints
# (Mounted at both /api/... and /api/v1/... for backwards compatibility)
# ============================================================================

@router.post(
    "/api/simulation/run",
    response_model=SimulationResult,
    summary="Run baseline architecture simulation",
    tags=["Simulation"],
)
@router.post(
    "/api/v1/simulation/run",
    response_model=SimulationResult,
    summary="Run baseline architecture simulation",
    tags=["Simulation"],
)
def api_run_simulation(payload: SimulationRunRequest) -> SimulationResult:
    """Execute baseline discrete-event architecture simulation."""
    try:
        return run_simulation(
            architecture=payload.architecture,
            workload=payload.workload,
            constraints=payload.constraints,
        )
    except SimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Simulation error: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception("Unexpected error during simulation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during simulation.",
        )


@router.post(
    "/api/optimization/run",
    response_model=OptimizationResult,
    summary="Optimize architecture candidates",
    tags=["Optimization"],
)
@router.post(
    "/api/v1/optimization/run",
    response_model=OptimizationResult,
    summary="Optimize architecture candidates",
    tags=["Optimization"],
)
async def api_optimize_architecture(payload: OptimizationRunRequest) -> OptimizationResult:
    """Run candidate generation, multi-candidate simulation, and multi-objective ranking."""
    try:
        opt_res = optimize_architecture(
            architecture=payload.architecture,
            workload=payload.workload,
            constraints=payload.constraints,
            objective=payload.objective,
            max_candidates=payload.max_candidates,
        )
        try:
            from backend.ai_agent.providers import get_ai_provider
            ai_provider = get_ai_provider()
            ai_narrative = await ai_provider.explain_optimization(
                baseline_metrics=opt_res.baseline_metrics,
                candidates=opt_res.ranked_candidates,
                recommended=opt_res.recommended_candidate,
                objective=payload.objective.value if hasattr(payload.objective, "value") else str(payload.objective),
            )
            if ai_narrative and len(ai_narrative.strip()) > 0:
                opt_res.trade_off_analysis = f"{opt_res.trade_off_analysis}\n\n[AI Model Explanation - {ai_provider.name.upper()} ({ai_provider.model_name})]:\n{ai_narrative}"
        except Exception as ai_err:
            logger.warning("AI optimization explanation skipped: %s", ai_err)

        return opt_res
    except SimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Simulation error during optimization: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception("Unexpected error during optimization: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during optimization.",
        )


@router.post(
    "/api/chaos/run",
    response_model=FailureSimulationResult,
    summary="Run chaos failure resilience simulation",
    tags=["Resilience"],
)
@router.post(
    "/api/v1/chaos/run",
    response_model=FailureSimulationResult,
    summary="Run chaos failure resilience simulation",
    tags=["Resilience"],
)
async def api_simulate_failure(payload: ChaosRunRequest) -> FailureSimulationResult:
    """Inject failure scenario and compute resilience comparisons."""
    try:
        chaos_res = simulate_failure(
            architecture=payload.architecture,
            workload=payload.workload,
            scenario=payload.scenario,
            constraints=payload.constraints,
        )
        try:
            from backend.ai_agent.providers import get_ai_provider
            ai_provider = get_ai_provider()
            ai_chaos_narrative = await ai_provider.explain_chaos(
                scenario=payload.scenario,
                baseline_metrics=chaos_res.baseline_metrics,
                failure_metrics=chaos_res.failure_metrics,
                affected_components=chaos_res.affected_components,
                recovered=chaos_res.recovery_observed,
            )
            if ai_chaos_narrative and len(ai_chaos_narrative.strip()) > 0:
                chaos_res.resilience_summary = f"{chaos_res.resilience_summary}\n\n[AI Resilience Analysis - {ai_provider.name.upper()} ({ai_provider.model_name})]:\n{ai_chaos_narrative}"
        except Exception as ai_err:
            logger.warning("AI chaos explanation skipped: %s", ai_err)

        return chaos_res
    except SimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Simulation error during chaos test: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception("Unexpected error during chaos simulation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during chaos simulation.",
        )


# ============================================================================
# Simulator Integration Endpoints (POST /api/v1/simulate/...)
# ============================================================================

@router.post(
    "/api/v1/simulate/baseline",
    response_model=BaselineSimulationResponse,
    summary="Run Baseline Simulation (Member 2 Engine)",
    tags=["Simulation Integration"],
)
async def simulate_baseline(payload: BaselineSimulationRequest) -> BaselineSimulationResponse:
    """
    Simulates baseline performance for a Member 1 validated Architecture graph.
    Powered by Member 2's real discrete-event SimulationEngine.
    """
    try:
        m2_graph, m2_workload, m2_constraints = adapt_m1_architecture_to_m2(payload.architecture)
        sim_result = run_simulation(
            architecture=m2_graph,
            workload=m2_workload,
            constraints=m2_constraints,
        )
        resp = adapt_m2_simulation_to_m1_baseline(payload.run_id, sim_result, payload.architecture)
        _BASELINE_STORE[payload.run_id] = (payload.architecture, resp)
        return resp
    except SimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ERR_SIMULATION_FAILED", "message": f"Simulation error: {str(e)}"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ERR_VALIDATION_FAILED", "message": f"Validation error: {str(e)}"},
        )
    except Exception as e:
        logger.exception("Baseline simulation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ERR_SIMULATION_INTERNAL", "message": str(e)},
        )


@router.post(
    "/api/v1/simulate/diagnostic",
    response_model=DiagnosticExperimentResponse,
    summary="Run Diagnostic Simulation Experiment (Member 2 Engine)",
    tags=["Simulation Integration"],
)
async def simulate_diagnostic(payload: DiagnosticExperimentRequest) -> DiagnosticExperimentResponse:
    """
    Executes a targeted diagnostic experiment using Member 2's SimulationEngine.
    Computes exact MetricDiffs against baseline measurements.
    """
    stored = _BASELINE_STORE.get(payload.baseline_run_id)
    if not stored:
        # Search in-memory investigations
        for inv in _INVESTIGATIONS_DB.values():
            base = inv.get("baseline")
            if base and getattr(base, "run_id", None) == payload.baseline_run_id:
                stored = (inv.get("architecture"), base)
                break

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ERR_BASELINE_NOT_FOUND",
                "message": f"Baseline run '{payload.baseline_run_id}' not found.",
            },
        )

    arch, baseline_resp = stored
    try:
        return run_adapted_diagnostic_experiment(payload, baseline_resp, arch)
    except SimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ERR_DIAGNOSTIC_FAILED", "message": f"Simulation error: {str(e)}"},
        )
    except Exception as e:
        logger.exception("Diagnostic simulation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ERR_DIAGNOSTIC_INTERNAL", "message": str(e)},
        )


# ============================================================================
# Member 1 Architecture Analysis & Root-Cause Investigation Endpoints
# ============================================================================

@router.post(
    "/api/v1/architecture/analyze",
    response_model=ArchitectureAnalyzeResponse,
    summary="Analyze Architecture Diagram and Requirements",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image or architecture"},
        502: {"model": ErrorResponse, "description": "Model API failure"},
    },
    tags=["Architecture Analysis"],
)
async def analyze_architecture(
    image: Optional[UploadFile] = File(None, description="Architecture diagram image (PNG, JPEG, WEBP)"),
    requirements: Optional[str] = Form(None, description="Textual system requirements or specifications"),
    workload_json: Optional[str] = Form(None, description="Optional JSON string for Workload"),
    constraints_json: Optional[str] = Form(None, description="Optional JSON string for Constraints"),
):
    """
    Ingests an architecture diagram image and user requirements.
    Uses Gemma/Gemini to extract components, connections, workload, and constraints,
    then executes graph validation.
    """
    image_bytes = None
    filename = "upload.png"
    if image:
        filename = image.filename or "upload.png"
        image_bytes = await image.read()

    user_workload = None
    if workload_json:
        try:
            user_workload = json.loads(workload_json)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ERR_INVALID_WORKLOAD_JSON", "message": f"Invalid workload_json: {e}"},
            )

    user_constraints = None
    if constraints_json:
        try:
            user_constraints = json.loads(constraints_json)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "ERR_INVALID_CONSTRAINTS_JSON", "message": f"Invalid constraints_json: {e}"},
            )

    parser = get_architecture_parser()
    try:
        result = await parser.analyze_architecture(
            image_bytes=image_bytes,
            filename=filename,
            user_requirements=requirements,
            user_workload=user_workload,
            user_constraints=user_constraints,
        )
        return result

    except ImageValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": e.code, "message": e.message},
        )
    except ModelClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": e.code, "message": e.message},
        )
    except Exception as e:
        logger.exception("Unexpected error analyzing architecture: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ERR_INTERNAL", "message": str(e)},
        )


@router.post(
    "/api/v1/investigations",
    response_model=InvestigationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Root-Cause Investigation on Validated Architecture",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid architecture input"},
        503: {"model": ErrorResponse, "description": "Simulator unavailable"},
    },
    tags=["Root Cause Investigation"],
)
async def start_investigation(
    payload: StartInvestigationRequest,
):
    """
    Runs an end-to-end investigation:
    1. Requests baseline simulation from Member 2's simulator engine.
    2. Generates root-cause hypotheses based on observed measurements.
    3. Executes targeted diagnostic experiments within safety limits.
    4. Builds and validates the Member 2 Optimization Handoff.
    """
    investigation_id = f"inv-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    architecture = payload.architecture

    # Initialize investigation record
    _INVESTIGATIONS_DB[investigation_id] = {
        "investigation_id": investigation_id,
        "status": InvestigationStatus.IN_PROGRESS,
        "created_at": now_iso,
        "updated_at": now_iso,
        "architecture_id": architecture.architecture_id,
        "architecture": architecture,
        "baseline": None,
        "root_cause_analysis": None,
        "handoff": None,
        "handoff_ready": False,
        "error": None,
    }

    sim_client = get_simulator_client()
    investigator = get_root_cause_investigator(sim_client)
    handoff_builder = get_handoff_builder()

    # Step 1: Run baseline simulation
    baseline_run_id = f"base-{investigation_id}"
    baseline_req = BaselineSimulationRequest(
        run_id=baseline_run_id,
        architecture=architecture,
        timeout_seconds=payload.timeout_seconds,
    )

    try:
        baseline_resp = await sim_client.run_baseline(baseline_req)
        _INVESTIGATIONS_DB[investigation_id]["baseline"] = baseline_resp
        _BASELINE_STORE[baseline_run_id] = (architecture, baseline_resp)
    except SimulatorTimeoutError as e:
        _INVESTIGATIONS_DB[investigation_id]["status"] = InvestigationStatus.FAILED
        _INVESTIGATIONS_DB[investigation_id]["error"] = e.message
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail={"error_code": e.code, "message": e.message})
    except SimulatorUnavailableError as e:
        _INVESTIGATIONS_DB[investigation_id]["status"] = InvestigationStatus.FAILED
        _INVESTIGATIONS_DB[investigation_id]["error"] = e.message
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"error_code": e.code, "message": e.message})
    except SimulatorClientError as e:
        _INVESTIGATIONS_DB[investigation_id]["status"] = InvestigationStatus.FAILED
        _INVESTIGATIONS_DB[investigation_id]["error"] = e.message
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": e.code, "message": e.message})

    # Step 2: Run root-cause investigation
    try:
        root_cause_result = await investigator.investigate(
            architecture=architecture,
            baseline=baseline_resp,
            investigation_id=investigation_id,
        )
        _INVESTIGATIONS_DB[investigation_id]["root_cause_analysis"] = root_cause_result
    except Exception as e:
        logger.exception("Investigation failed during root-cause analysis: %s", e)
        _INVESTIGATIONS_DB[investigation_id]["status"] = InvestigationStatus.FAILED
        _INVESTIGATIONS_DB[investigation_id]["error"] = str(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ERR_INVESTIGATION_FAILED", "message": str(e)},
        )

    # Step 3: Build Member 2 Optimization Handoff
    validation_summary = ArchitectureValidationResult(
        valid=True,
        issues=[],
        assumptions=[],
        unresolved_questions=[],
    )

    handoff = handoff_builder.build_handoff(
        investigation_id=investigation_id,
        architecture=architecture,
        validation_result=validation_summary,
        baseline=baseline_resp,
        root_cause_result=root_cause_result,
    )

    _INVESTIGATIONS_DB[investigation_id]["handoff"] = handoff
    _INVESTIGATIONS_DB[investigation_id]["handoff_ready"] = True
    _INVESTIGATIONS_DB[investigation_id]["status"] = root_cause_result.status
    _INVESTIGATIONS_DB[investigation_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _INVESTIGATIONS_DB[investigation_id]["execution_mode"] = "mock" if (baseline_resp and baseline_resp.is_mock) else "real"
    _INVESTIGATIONS_DB[investigation_id]["engine_name"] = "deterministic_mock" if (baseline_resp and baseline_resp.is_mock) else "discrete_event_engine"
    _INVESTIGATIONS_DB[investigation_id]["request_id"] = investigation_id

    return InvestigationDetailResponse(
        investigation_id=investigation_id,
        status=_INVESTIGATIONS_DB[investigation_id]["status"],
        created_at=_INVESTIGATIONS_DB[investigation_id]["created_at"],
        updated_at=_INVESTIGATIONS_DB[investigation_id]["updated_at"],
        architecture_id=architecture.architecture_id,
        baseline=baseline_resp,
        root_cause_analysis=root_cause_result,
        handoff_ready=True,
        execution_mode=_INVESTIGATIONS_DB[investigation_id]["execution_mode"],
        engine_name=_INVESTIGATIONS_DB[investigation_id]["engine_name"],
        request_id=investigation_id,
    )


@router.get(
    "/api/v1/investigations/{investigation_id}",
    response_model=InvestigationDetailResponse,
    summary="Get Investigation Status and Findings",
    tags=["Root Cause Investigation"],
)
async def get_investigation(investigation_id: str):
    """
    Retrieves the current status and detailed findings of an investigation.
    """
    record = _INVESTIGATIONS_DB.get(investigation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ERR_INVESTIGATION_NOT_FOUND", "message": f"Investigation '{investigation_id}' not found"},
        )

    return InvestigationDetailResponse(
        investigation_id=record["investigation_id"],
        status=record["status"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        architecture_id=record["architecture_id"],
        baseline=record.get("baseline"),
        root_cause_analysis=record.get("root_cause_analysis"),
        handoff_ready=record.get("handoff_ready", False),
        error=record.get("error"),
        execution_mode=record.get("execution_mode", "real"),
        engine_name=record.get("engine_name", "discrete_event_engine"),
        request_id=record.get("request_id", investigation_id),
    )


@router.get(
    "/api/v1/investigations/{investigation_id}/handoff",
    response_model=Member1Handoff,
    summary="Get Validated Member 2 Optimization Handoff JSON",
    tags=["Root Cause Investigation"],
)
async def get_investigation_handoff(investigation_id: str):
    """
    Returns the validated, structured handoff JSON ready for Member 2's optimizer.
    """
    record = _INVESTIGATIONS_DB.get(investigation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ERR_INVESTIGATION_NOT_FOUND", "message": f"Investigation '{investigation_id}' not found"},
        )

    handoff = record.get("handoff")
    if not handoff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "ERR_HANDOFF_NOT_READY",
                "message": f"Handoff for investigation '{investigation_id}' is not yet available. Status: {record['status']}",
            },
        )

    return handoff
