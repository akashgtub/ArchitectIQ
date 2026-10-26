"""FastAPI routes for ArchitectIQ architecture simulation, optimization, and chaos testing.

Provides standalone API endpoints that can be included by the integration owner
into the main FastAPI application via `app.include_router(router)`.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.service import optimize_architecture, run_simulation, simulate_failure
from backend.simulator.engine import SimulationError
from backend.simulator.schemas import (
    ArchitectureGraph,
    Constraints,
    FailureScenario,
    FailureSimulationResult,
    OptimizationObjective,
    OptimizationResult,
    SimulationResult,
    WorkloadConfig,
)

router = APIRouter(prefix="/api", tags=["simulation", "optimization", "chaos"])


class SimulationRunRequest(BaseModel):
    """Payload for running baseline architecture simulation."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph = Field(..., description="Architecture topology graph")
    workload: WorkloadConfig = Field(..., description="Simulation workload profile")
    constraints: Optional[Constraints] = Field(None, description="Optional performance and budget constraints")


class OptimizationRunRequest(BaseModel):
    """Payload for architecture optimization search."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph = Field(..., description="Baseline architecture topology graph")
    workload: WorkloadConfig = Field(..., description="Simulation workload profile")
    constraints: Optional[Constraints] = Field(None, description="Boundary performance and budget constraints")
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
    constraints: Optional[Constraints] = Field(None, description="Optional performance and budget constraints")


@router.post(
    "/simulation/run",
    response_model=SimulationResult,
    summary="Run baseline architecture simulation",
    description="Simulates discrete request flow across the architecture graph under the given workload.",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during simulation.",
        )


@router.post(
    "/optimization/run",
    response_model=OptimizationResult,
    summary="Optimize architecture candidates",
    description="Explores alternative architecture topologies, simulates each candidate under identical workload conditions, and ranks candidates against objectives.",
)
def api_optimize_architecture(payload: OptimizationRunRequest) -> OptimizationResult:
    """Run candidate generation, multi-candidate simulation, and multi-objective ranking."""
    try:
        return optimize_architecture(
            architecture=payload.architecture,
            workload=payload.workload,
            constraints=payload.constraints,
            objective=payload.objective,
            max_candidates=payload.max_candidates,
        )
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during optimization.",
        )


@router.post(
    "/chaos/run",
    response_model=FailureSimulationResult,
    summary="Run chaos failure resilience simulation",
    description="Simulates isolated component failure scenarios (crash, slowdown, outage, timeout, spike) and compares degraded vs baseline metrics.",
)
def api_simulate_failure(payload: ChaosRunRequest) -> FailureSimulationResult:
    """Inject failure scenario and compute resilience comparisons."""
    try:
        return simulate_failure(
            architecture=payload.architecture,
            workload=payload.workload,
            scenario=payload.scenario,
            constraints=payload.constraints,
        )
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during chaos simulation.",
        )
