"""ArchitectIQ Simulation Package.

Provides workload generation, queueing and discrete-event simulation,
performance metrics computation, and provisional schemas for architecture modeling.
"""

from backend.simulator.engine import SimulationEngine, SimulationError
from backend.simulator.performance import (
    calculate_component_cost,
    calculate_latencies,
    compile_performance_metrics,
    evaluate_constraints,
    identify_bottlenecks,
)
from backend.simulator.schemas import (
    ArchitectureGraph,
    BottleneckInfo,
    CandidateArchitecture,
    Component,
    ComponentMetrics,
    ComponentType,
    Connection,
    Constraints,
    ConstraintViolation,
    FailureScenario,
    FailureSimulationResult,
    FailureType,
    OptimizationObjective,
    OptimizationRequest,
    OptimizationResult,
    PathType,
    PerformanceMetrics,
    SeverityLevel,
    SimulationResult,
    WorkloadConfig,
    WorkloadPattern,
)
from backend.simulator.workload import SimulatedRequest, WorkloadGenerator, WorkloadStep

__all__ = [
    "ArchitectureGraph",
    "BottleneckInfo",
    "CandidateArchitecture",
    "Component",
    "ComponentMetrics",
    "ComponentType",
    "Connection",
    "Constraints",
    "ConstraintViolation",
    "FailureScenario",
    "FailureSimulationResult",
    "FailureType",
    "OptimizationObjective",
    "OptimizationRequest",
    "OptimizationResult",
    "PathType",
    "PerformanceMetrics",
    "SeverityLevel",
    "SimulatedRequest",
    "SimulationEngine",
    "SimulationError",
    "SimulationResult",
    "WorkloadConfig",
    "WorkloadGenerator",
    "WorkloadPattern",
    "WorkloadStep",
    "calculate_component_cost",
    "calculate_latencies",
    "compile_performance_metrics",
    "evaluate_constraints",
    "identify_bottlenecks",
]
