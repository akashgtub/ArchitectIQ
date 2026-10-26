"""Pydantic v2 schemas for ArchitectIQ simulation, optimization, and chaos engineering.

Defines the provisional integration contract between Member 1 (AI extraction / validation)
and Member 2 (workload simulation, performance analysis, optimizer, chaos lab).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ComponentType(str, Enum):
    """Supported architecture component types."""
    LOAD_BALANCER = "load_balancer"
    API_SERVER = "api_server"
    CACHE = "cache"
    DATABASE = "database"
    MESSAGE_BROKER = "message_broker"
    QUEUE = "queue"
    THIRD_PARTY_SERVICE = "third_party_service"
    STORAGE = "storage"


class PathType(str, Enum):
    """Traffic path type handled by a connection."""
    BOTH = "both"
    READ = "read"
    WRITE = "write"


class WorkloadPattern(str, Enum):
    """Traffic generation profile."""
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    BURST = "burst"
    SPIKE = "spike"


class SeverityLevel(str, Enum):
    """Severity level for bottlenecks and issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureType(str, Enum):
    """Failure simulation scenario types."""
    API_CRASH = "api_crash"
    DB_SLOWDOWN = "db_slowdown"
    DB_OUTAGE = "db_outage"
    CACHE_OUTAGE = "cache_outage"
    TIMEOUT = "timeout"
    LATENCY_INCREASE = "latency_increase"
    TRAFFIC_SPIKE = "traffic_spike"
    REPLICA_LOSS = "replica_loss"


class OptimizationObjective(str, Enum):
    """Optimization objectives for candidate ranking."""
    MINIMIZE_LATENCY = "minimize_latency"
    MINIMIZE_COST = "minimize_cost"
    MAXIMIZE_THROUGHPUT = "maximize_throughput"
    BALANCED = "balanced"


# Default estimated monthly costs per replica tier (USD)
DEFAULT_COST_PER_MONTH: Dict[ComponentType, float] = {
    ComponentType.LOAD_BALANCER: 25.0,
    ComponentType.API_SERVER: 40.0,
    ComponentType.CACHE: 60.0,
    ComponentType.DATABASE: 120.0,
    ComponentType.MESSAGE_BROKER: 50.0,
    ComponentType.QUEUE: 30.0,
    ComponentType.THIRD_PARTY_SERVICE: 20.0,
    ComponentType.STORAGE: 15.0,
}


class Component(BaseModel):
    """A node in the architecture graph representing a computing, caching, or data unit."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique component identifier (e.g., 'api-1', 'cache-1')")
    type: ComponentType = Field(..., description="Component type enum")
    name: Optional[str] = Field(None, description="Human-readable label for the component")
    capacity_rps: float = Field(
        ...,
        gt=0,
        description="Peak requests-per-second capacity for a single replica before saturation"
    )
    replicas: int = Field(
        default=1,
        ge=1,
        description="Total active running instances of this component (total capacity = capacity_rps * replicas)"
    )
    base_latency_ms: float = Field(
        default=5.0,
        ge=0.0,
        description="Intrinsic base execution latency in milliseconds without queueing delays"
    )
    cost_per_month_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Monthly cost in USD per replica. If 0.0, standard tier default will be applied"
    )
    cache_hit_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Applicable when type == 'cache'. Fraction of read traffic served from cache (0.0 to 1.0)"
    )
    max_queue_size: int = Field(
        default=1000,
        ge=0,
        description="Maximum requests queued before dropping (excess causes error rate increase)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provisional extension metadata bucket from Member 1's AI diagram extraction"
    )

    @model_validator(mode="after")
    def populate_defaults_and_validate(self) -> Component:
        # Default cost assignment if left at 0.0
        if self.cost_per_month_usd == 0.0 and self.type in DEFAULT_COST_PER_MONTH:
            self.cost_per_month_usd = DEFAULT_COST_PER_MONTH[self.type]
        # Default cache hit ratio if type is cache and not explicitly set
        if self.type == ComponentType.CACHE and self.cache_hit_ratio is None:
            self.cache_hit_ratio = 0.8
        return self


class Connection(BaseModel):
    """A directed edge in the architecture graph representing network communication."""
    model_config = ConfigDict(extra="ignore")

    source: str = Field(..., description="Origin component ID")
    target: str = Field(..., description="Destination component ID")
    protocol: Optional[str] = Field(default="http", description="Communication protocol (e.g., http, grpc, redis, sql)")
    latency_overhead_ms: float = Field(
        default=1.0,
        ge=0.0,
        description="Network transport and serialization round-trip latency overhead in ms"
    )
    path_type: PathType = Field(
        default=PathType.BOTH,
        description="Specifies whether connection handles read, write, or both traffic types"
    )

    @field_validator("source", "target")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Component ID cannot be empty or whitespace")
        return v.strip()


class ArchitectureGraph(BaseModel):
    """Validated architecture topology graph composed of components and connections."""
    model_config = ConfigDict(extra="ignore")

    components: List[Component] = Field(..., min_length=1, description="List of architecture components")
    connections: List[Connection] = Field(default_factory=list, description="Directed connections between components")

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> ArchitectureGraph:
        component_ids = {c.id for c in self.components}
        if len(component_ids) != len(self.components):
            duplicates = [c.id for c in self.components if self.components.count(c) > 1]
            raise ValueError(f"Duplicate component IDs detected in architecture: {set(duplicates)}")

        for conn in self.connections:
            if conn.source not in component_ids:
                raise ValueError(
                    f"Connection source '{conn.source}' does not exist in component list: {sorted(component_ids)}"
                )
            if conn.target not in component_ids:
                raise ValueError(
                    f"Connection target '{conn.target}' does not exist in component list: {sorted(component_ids)}"
                )
            if conn.source == conn.target:
                raise ValueError(f"Self-loop connection detected on component '{conn.source}'")

        return self

    def get_component(self, component_id: str) -> Optional[Component]:
        """Look up a component by ID."""
        for c in self.components:
            if c.id == component_id:
                return c
        return None

    def get_outgoing_connections(self, component_id: str) -> List[Connection]:
        """Get all connections originating from component_id."""
        return [c for c in self.connections if c.source == component_id]

    def get_incoming_connections(self, component_id: str) -> List[Connection]:
        """Get all connections terminating at component_id."""
        return [c for c in self.connections if c.target == component_id]

    def get_entry_points(self) -> List[Component]:
        """Identify entry-point components (load balancers or API servers with in-degree 0)."""
        # Prioritize load balancers
        lbs = [c for c in self.components if c.type == ComponentType.LOAD_BALANCER]
        if lbs:
            return lbs

        # Next: API servers with no incoming connections
        targets = {c.target for c in self.connections}
        api_servers = [
            c for c in self.components
            if c.type == ComponentType.API_SERVER and c.id not in targets
        ]
        if api_servers:
            return api_servers

        # Components with in-degree 0 that have outgoing connections
        sources = {c.source for c in self.connections}
        in_degree_zero_connected = [
            c for c in self.components
            if c.id not in targets and (c.id in sources or len(self.components) == 1)
        ]
        if in_degree_zero_connected:
            return in_degree_zero_connected

        # Fallback to any in-degree zero component
        in_degree_zero = [c for c in self.components if c.id not in targets]
        if in_degree_zero:
            return in_degree_zero

        return [self.components[0]]


class WorkloadConfig(BaseModel):
    """Workload generation parameters for traffic simulation."""
    model_config = ConfigDict(extra="ignore")

    requests_per_second: float = Field(..., gt=0, description="Target requests per second (RPS)")
    read_ratio: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Fraction of requests that are reads (0.0 = all writes, 1.0 = all reads)"
    )
    duration_seconds: float = Field(default=60.0, gt=0, description="Simulation horizon in seconds")
    pattern: WorkloadPattern = Field(default=WorkloadPattern.CONSTANT, description="Traffic profile pattern")
    burst_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier applied to base RPS during burst or spike intervals"
    )
    burst_start_sec: float = Field(
        default=20.0,
        ge=0.0,
        description="Start time (seconds into simulation) of burst or spike"
    )
    burst_duration_sec: float = Field(
        default=10.0,
        ge=0.0,
        description="Duration of burst or spike in seconds"
    )
    seed: int = Field(default=42, description="Random seed for deterministic reproducible simulation")
    step_size_sec: float = Field(
        default=1.0,
        gt=0.0,
        le=10.0,
        description="Discrete time step resolution in seconds"
    )


class Constraints(BaseModel):
    """Performance and financial boundary constraints."""
    model_config = ConfigDict(extra="ignore")

    max_p95_latency_ms: Optional[float] = Field(None, gt=0, description="Max acceptable p95 latency in ms")
    max_p99_latency_ms: Optional[float] = Field(None, gt=0, description="Max acceptable p99 latency in ms")
    monthly_budget_usd: Optional[float] = Field(None, gt=0, description="Max acceptable monthly infrastructure cost")
    min_throughput_rps: Optional[float] = Field(None, gt=0, description="Min acceptable completed throughput")
    max_error_rate: Optional[float] = Field(None, ge=0.0, le=1.0, description="Max acceptable error rate (0.0 to 1.0)")


class ComponentMetrics(BaseModel):
    """Detailed performance and utilization metrics for a single component."""
    model_config = ConfigDict(extra="ignore")

    component_id: str
    component_type: ComponentType
    replicas: int
    effective_capacity_rps: float
    offered_rps: float
    throughput_rps: float
    dropped_rps: float
    utilization: float
    mean_queue_depth: float
    mean_service_time_ms: float
    mean_queue_time_ms: float
    total_latency_ms: float
    is_bottleneck: bool
    cost_per_month_usd: float


class PerformanceMetrics(BaseModel):
    """Aggregated end-to-end performance results for an architecture under workload."""
    model_config = ConfigDict(extra="ignore")

    mean_latency_ms: float = Field(..., ge=0, description="Mean end-to-end request latency in ms")
    p50_latency_ms: float = Field(..., ge=0, description="50th percentile (median) latency in ms")
    p95_latency_ms: float = Field(..., ge=0, description="95th percentile latency in ms")
    p99_latency_ms: float = Field(..., ge=0, description="99th percentile latency in ms")
    throughput_rps: float = Field(..., ge=0, description="Total successfully processed RPS")
    error_rate: float = Field(..., ge=0, le=1.0, description="Fraction of dropped or failed requests")
    completed_requests: int = Field(..., ge=0, description="Total number of successfully completed requests")
    dropped_requests: int = Field(..., ge=0, description="Total dropped or failed requests")
    total_monthly_cost_usd: float = Field(..., ge=0, description="Estimated total monthly infrastructure cost")
    component_breakdown: Dict[str, ComponentMetrics] = Field(
        default_factory=dict,
        description="Per-component metrics breakdown"
    )


class BottleneckInfo(BaseModel):
    """Diagnosed system bottleneck with severity and suggested mitigation."""
    model_config = ConfigDict(extra="ignore")

    component_id: str
    severity: SeverityLevel
    reason: str
    utilization: float
    recommended_action: str


class ConstraintViolation(BaseModel):
    """Details of a broken constraint."""
    model_config = ConfigDict(extra="ignore")

    constraint_name: str
    threshold: float
    actual_value: float
    message: str


class SimulationResult(BaseModel):
    """Top-level output returned by the simulation engine."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'success', 'degraded', or 'failed'")
    simulation_type: str = Field(default="baseline", description="'baseline', 'optimized', or 'chaos_resilience'")
    metrics: PerformanceMetrics
    bottlenecks: List[BottleneckInfo] = Field(default_factory=list)
    constraint_violations: List[ConstraintViolation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    simulation_metadata: Dict[str, Any] = Field(default_factory=dict)


class FailureScenario(BaseModel):
    """Chaos engineering fault injection scenario."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Descriptive scenario name")
    failure_type: FailureType = Field(..., description="Fault type to inject")
    target_component_id: Optional[str] = Field(
        default=None,
        description="Target component ID (required for component-specific failures, ignored for global traffic spike)"
    )
    start_time_sec: float = Field(default=10.0, ge=0.0, description="Time into simulation when fault begins")
    duration_sec: Optional[float] = Field(
        default=20.0,
        gt=0.0,
        description="Duration of fault in seconds (None means permanent for simulation duration)"
    )
    degradation_factor: float = Field(
        default=2.0,
        ge=0.0,
        description="Magnitude of degradation (e.g. 3.0x latency, 0.5 replica loss, 0.0 complete outage)"
    )
    recovery_mode: Optional[str] = Field(
        default="instant_recovery",
        description="'instant_recovery', 'linear_recovery', or 'none'"
    )


class FailureSimulationResult(BaseModel):
    """Resilience testing comparison output."""
    model_config = ConfigDict(extra="ignore")

    status: str
    scenario: FailureScenario
    affected_components: List[str]
    baseline_metrics: PerformanceMetrics
    failure_metrics: PerformanceMetrics
    latency_delta_ms: float
    throughput_delta_rps: float
    error_rate_delta: float
    redundancy_supported: bool
    recovery_observed: bool
    bottlenecks: List[BottleneckInfo]
    resilience_summary: str


class CandidateArchitecture(BaseModel):
    """An optimized candidate architecture variation evaluated by the optimizer."""
    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    description: str
    modifications: List[str]
    architecture: ArchitectureGraph
    metrics: PerformanceMetrics
    constraint_violations: List[ConstraintViolation]
    is_feasible: bool
    objective_score: float
    rank: Optional[int] = None


class OptimizationRequest(BaseModel):
    """Input payload for architecture optimization."""
    model_config = ConfigDict(extra="ignore")

    architecture: ArchitectureGraph
    workload: WorkloadConfig
    constraints: Optional[Constraints] = None
    objective: OptimizationObjective = Field(
        default=OptimizationObjective.BALANCED,
        description="Target optimization objective"
    )
    max_candidates: int = Field(default=8, ge=1, le=50, description="Maximum candidates to generate and evaluate")


class OptimizationResult(BaseModel):
    """Output payload from architecture optimization."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'success', 'no_feasible_candidate', or 'failed'")
    objective: OptimizationObjective
    baseline_metrics: PerformanceMetrics
    total_candidates_evaluated: int
    feasible_candidates_count: int
    recommended_candidate: Optional[CandidateArchitecture] = None
    ranked_candidates: List[CandidateArchitecture] = Field(default_factory=list)
    trade_off_analysis: str
