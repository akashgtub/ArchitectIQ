"""
ArchPilot AI - API Endpoints
Member 1: Architecture Understanding & Root-Cause Investigation

Defines the HTTP interface:
- POST /api/v1/architecture/analyze
- POST /api/v1/investigations
- GET  /api/v1/investigations/{investigation_id}
- GET  /api/v1/investigations/{investigation_id}/handoff
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

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
from backend.shared.schemas import (
    Architecture,
    ArchitectureAnalyzeResponse,
    ArchitectureValidationResult,
    BaselineSimulationRequest,
    BaselineSimulationResponse,
    ErrorResponse,
    InvestigationDetailResponse,
    InvestigationStatus,
    Member1Handoff,
    RootCauseAnalysisResult,
    StartInvestigationRequest,
)

logger = logging.getLogger("archpilot.api")

router = APIRouter(prefix="/api/v1")

# In-memory store for investigations
# Suitable for pair-programming and development test workflow
_INVESTIGATIONS_DB: Dict[str, Dict[str, Any]] = {}


def get_architecture_parser() -> ArchitectureParserService:
    return ArchitectureParserService()


def get_simulator_client() -> SimulatorClient:
    return SimulatorClient()


def get_root_cause_investigator(sim_client: SimulatorClient) -> RootCauseInvestigator:
    return RootCauseInvestigator(simulator_client=sim_client)


def get_handoff_builder() -> HandoffBuilder:
    return HandoffBuilder()


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "healthy",
        "service": "ArchPilot AI - Member 1 (Architecture Understanding & Root-Cause)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/architecture/analyze",
    response_model=ArchitectureAnalyzeResponse,
    summary="Analyze Architecture Diagram and Requirements",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image or architecture"},
        502: {"model": ErrorResponse, "description": "Model API failure"},
    },
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
    "/investigations",
    response_model=InvestigationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Root-Cause Investigation on Validated Architecture",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid architecture input"},
        503: {"model": ErrorResponse, "description": "Simulator unavailable"},
    },
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

    return InvestigationDetailResponse(
        investigation_id=investigation_id,
        status=_INVESTIGATIONS_DB[investigation_id]["status"],
        created_at=_INVESTIGATIONS_DB[investigation_id]["created_at"],
        updated_at=_INVESTIGATIONS_DB[investigation_id]["updated_at"],
        architecture_id=architecture.architecture_id,
        baseline=baseline_resp,
        root_cause_analysis=root_cause_result,
        handoff_ready=True,
    )


@router.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationDetailResponse,
    summary="Get Investigation Status and Findings",
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
    )


@router.get(
    "/investigations/{investigation_id}/handoff",
    response_model=Member1Handoff,
    summary="Get Validated Member 2 Optimization Handoff JSON",
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
