"""Service facade for ArchitectIQ simulation, optimization, and chaos engineering.

Provides unified, type-safe functional entry points for running simulations,
optimizing architectures, and testing resilience scenarios.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from backend.chaos_lab.failure_simulator import FailureSimulator
from backend.optimizer.optimizer import ArchitectureOptimizer
from backend.simulator.engine import SimulationEngine, SimulationError
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


def _coerce_architecture(arch: Union[ArchitectureGraph, Dict[str, Any]]) -> ArchitectureGraph:
    """Ensure architecture is a valid ArchitectureGraph instance."""
    if isinstance(arch, ArchitectureGraph):
        return arch
    if isinstance(arch, dict):
        return ArchitectureGraph(**arch)
    raise ValueError(f"Expected ArchitectureGraph or dict, got {type(arch).__name__}")


def _coerce_workload(workload: Union[WorkloadConfig, Dict[str, Any]]) -> WorkloadConfig:
    """Ensure workload is a valid WorkloadConfig instance."""
    if isinstance(workload, WorkloadConfig):
        return workload
    if isinstance(workload, dict):
        return WorkloadConfig(**workload)
    raise ValueError(f"Expected WorkloadConfig or dict, got {type(workload).__name__}")


def _coerce_constraints(
    constraints: Optional[Union[Constraints, Dict[str, Any]]],
) -> Optional[Constraints]:
    """Ensure constraints is a valid Constraints instance or None."""
    if constraints is None or isinstance(constraints, Constraints):
        return constraints
    if isinstance(constraints, dict):
        return Constraints(**constraints)
    raise ValueError(f"Expected Constraints or dict, got {type(constraints).__name__}")


def _coerce_scenario(scenario: Union[FailureScenario, Dict[str, Any]]) -> FailureScenario:
    """Ensure scenario is a valid FailureScenario instance."""
    if isinstance(scenario, FailureScenario):
        return scenario
    if isinstance(scenario, dict):
        return FailureScenario(**scenario)
    raise ValueError(f"Expected FailureScenario or dict, got {type(scenario).__name__}")


def run_simulation(
    architecture: Union[ArchitectureGraph, Dict[str, Any]],
    workload: Union[WorkloadConfig, Dict[str, Any]],
    constraints: Optional[Union[Constraints, Dict[str, Any]]] = None,
) -> SimulationResult:
    """Execute a baseline architecture simulation under the specified workload."""
    arch_obj = _coerce_architecture(architecture)
    workload_obj = _coerce_workload(workload)
    constraints_obj = _coerce_constraints(constraints)

    engine = SimulationEngine(
        graph=arch_obj,
        workload=workload_obj,
        constraints=constraints_obj,
    )
    return engine.run()


def optimize_architecture(
    architecture: Union[ArchitectureGraph, Dict[str, Any]],
    workload: Union[WorkloadConfig, Dict[str, Any]],
    constraints: Optional[Union[Constraints, Dict[str, Any]]] = None,
    objective: Union[OptimizationObjective, str] = OptimizationObjective.BALANCED,
    max_candidates: int = 8,
) -> OptimizationResult:
    """Generate, simulate, and rank candidate architecture optimizations."""
    arch_obj = _coerce_architecture(architecture)
    workload_obj = _coerce_workload(workload)
    constraints_obj = _coerce_constraints(constraints)

    if isinstance(objective, str):
        try:
            obj_enum = OptimizationObjective(objective.lower())
        except ValueError:
            valid_objs = [o.value for o in OptimizationObjective]
            raise ValueError(f"Invalid objective '{objective}'. Must be one of: {valid_objs}")
    else:
        obj_enum = objective

    optimizer = ArchitectureOptimizer(
        architecture=arch_obj,
        workload=workload_obj,
        constraints=constraints_obj,
        objective=obj_enum,
        max_candidates=max_candidates,
    )
    return optimizer.optimize()


def simulate_failure(
    architecture: Union[ArchitectureGraph, Dict[str, Any]],
    workload: Union[WorkloadConfig, Dict[str, Any]],
    scenario: Union[FailureScenario, Dict[str, Any]],
    constraints: Optional[Union[Constraints, Dict[str, Any]]] = None,
) -> FailureSimulationResult:
    """Inject a failure scenario and evaluate architecture resilience."""
    arch_obj = _coerce_architecture(architecture)
    workload_obj = _coerce_workload(workload)
    scenario_obj = _coerce_scenario(scenario)
    constraints_obj = _coerce_constraints(constraints)

    simulator = FailureSimulator(
        architecture=arch_obj,
        workload=workload_obj,
        scenario=scenario_obj,
        constraints=constraints_obj,
    )
    return simulator.simulate()
