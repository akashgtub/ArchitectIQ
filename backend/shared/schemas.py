"""
ArchPilot AI - Shared Data Contract
Schema Version: 1.0

This module defines the canonical Pydantic models for Member 1 and Member 2 data exchange.
It enforces strict validation, explicit assumptions, traceability of evidence,
and zero fabricated performance measurements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: str = "1.0"


# ============================================================================
# Enums
# ============================================================================

class ComponentType(str, Enum):
    API_SERVER = "api_server"
    WEB_SERVER = "web_server"
    LOAD_BALANCER = "load_balancer"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    OBJECT_STORAGE = "object_storage"
    MICROSERVICE = "microservice"
    GATEWAY = "gateway"
    WORKER = "worker"
    CDN = "cdn"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class ConnectionType(str, Enum):
    REQUEST = "request"                    # Synchronous request/response (e.g. HTTP/REST, gRPC)
    ASYNC_MESSAGE = "async_message"        # Asynchronous pub/sub or queue message
    DATA_ACCESS = "data_access"            # Read/write from persistence or cache
    DEPENDENCY = "dependency"              # Logical dependency or health check
    STREAM = "stream"                      # Continuous data stream (e.g. WebSocket, Kafka stream)


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ConfidenceLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HypothesisStatus(str, Enum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    TESTED_SUPPORTED = "tested_supported"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    TESTED_WEAKENED = "tested_weakened"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CLARIFICATION_REQUIRED = "clarification_required"


class SimulationStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SupportedDiagnosticExperiment(str, Enum):
    INCREASE_WORKLOAD = "increase_workload"
    VARY_READ_WRITE_MIX = "vary_read_write_mix"
    SIMULATE_DB_LATENCY = "simulate_db_latency"
    SCALE_COMPONENT = "scale_component"
    TOGGLE_CACHE = "toggle_cache"
    ISOLATE_DEPENDENCY = "isolate_dependency"


# ============================================================================
# Core Architecture Models
# ============================================================================

class Component(BaseModel):
    id: str = Field(..., description="Unique component identifier (e.g. 'api-1', 'db-primary')")
    type: ComponentType = Field(..., description="Standardized component type")
    name: Optional[str] = Field(None, description="Human readable label or display name")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Component-specific attributes (e.g. instances, cpu_cores, ram_gb, db_engine)"
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_component_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_lower = v.lower().strip()
            alias_map = {
                "api_gateway": ComponentType.GATEWAY,
                "service": ComponentType.MICROSERVICE,
                "queue": ComponentType.MESSAGE_QUEUE,
                "db": ComponentType.DATABASE,
            }
            if v_lower in alias_map:
                return alias_map[v_lower]
        return v

    @field_validator("id")
    @classmethod
    def validate_id_not_empty(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Component id cannot be empty or whitespace")
        return v_stripped


class Connection(BaseModel):
    source: str = Field(..., description="Source component ID")
    target: str = Field(..., description="Target component ID")
    type: ConnectionType = Field(default=ConnectionType.REQUEST, description="Connection communication pattern")
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Connection attributes (e.g. protocol, timeout_ms, connection_pool_size)"
    )

    @field_validator("source", "target")
    @classmethod
    def validate_endpoints_not_empty(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Connection endpoint id cannot be empty")
        return v_stripped


class Workload(BaseModel):
    requests_per_second: float = Field(..., ge=0.0, description="Baseline incoming load in RPS")
    read_ratio: float = Field(..., ge=0.0, le=1.0, description="Proportion of read operations (0.0 - 1.0)")
    write_ratio: float = Field(..., ge=0.0, le=1.0, description="Proportion of write operations (0.0 - 1.0)")
    peak_multiplier: Optional[float] = Field(None, ge=1.0, description="Multiplier for peak traffic burst")
    concurrent_users: Optional[int] = Field(None, ge=0, description="Estimated concurrent users")

    @model_validator(mode="after")
    def validate_ratios_sum(self) -> Workload:
        total = self.read_ratio + self.write_ratio
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"read_ratio ({self.read_ratio}) and write_ratio ({self.write_ratio}) must sum to 1.0 (got {total:.2f})"
            )
        return self


class Constraints(BaseModel):
    max_p95_latency_ms: Optional[float] = Field(None, gt=0.0, description="Target max p95 latency in ms")
    min_throughput_rps: Optional[float] = Field(None, ge=0.0, description="Target minimum throughput in RPS")
    max_cost_per_hour: Optional[float] = Field(None, ge=0.0, description="Target maximum cost budget in USD/hr")
    min_availability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Target minimum availability (e.g. 0.999)")


class Architecture(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION, description="Data contract version")
    architecture_id: str = Field(..., description="Unique architecture identifier")
    components: List[Component] = Field(default_factory=list, description="List of architecture components")
    connections: List[Connection] = Field(default_factory=list, description="List of directed connections")
    workload: Workload = Field(..., description="System workload specification")
    constraints: Constraints = Field(default_factory=Constraints, description="Target performance constraints")


# ============================================================================
# Validation and Ambiguity Models
# ============================================================================

class ValidationIssue(BaseModel):
    severity: ValidationSeverity = Field(..., description="Issue severity: info, warning, error")
    code: str = Field(..., description="Standardized issue code (e.g. 'ERR_DUPLICATE_ID', 'WARN_DISCONNECTED')")
    message: str = Field(..., description="Human readable description of the validation issue")
    affected_components: List[str] = Field(default_factory=list, description="IDs of affected components")
    requires_clarification: bool = Field(default=False, description="True if blocking simulation without user answer")


class ClarificationQuestion(BaseModel):
    question_id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="Clear question explaining what information is missing or ambiguous")
    affected_components: List[str] = Field(default_factory=list, description="Relevant components")
    category: str = Field(..., description="Category: workload, connection, component_type, capacity, cache_policy")
    suggested_options: Optional[List[str]] = Field(None, description="Optional suggested answers for the user")


class ArchitectureValidationResult(BaseModel):
    valid: bool = Field(..., description="True if architecture has no blocking errors and can proceed to baseline")
    issues: List[ValidationIssue] = Field(default_factory=list, description="List of detected validation issues")
    assumptions: List[str] = Field(default_factory=list, description="Explicit assumptions made during extraction")
    unresolved_questions: List[ClarificationQuestion] = Field(
        default_factory=list,
        description="Clarification questions requiring user response before reliable simulation"
    )


# ============================================================================
# Simulator Contract Models (Member 1 -> Member 2 Simulator)
# ============================================================================

class BaselineSimulationRequest(BaseModel):
    run_id: str = Field(..., description="Unique run identifier for tracing")
    architecture: Architecture = Field(..., description="Validated architecture model")
    timeout_seconds: Optional[int] = Field(default=30, ge=1, le=120, description="Simulator timeout limit")


class ComponentMetric(BaseModel):
    component_id: str = Field(..., description="Identifier of the measured component")
    cpu_utilization_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="CPU utilization percentage")
    memory_utilization_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="Memory utilization percentage")
    latency_p95_ms: Optional[float] = Field(None, ge=0.0, description="Component-level p95 processing latency in ms")
    throughput_rps: Optional[float] = Field(None, ge=0.0, description="Actual processed throughput in RPS")
    error_rate_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="Error rate percentage")


class BaselineSimulationResponse(BaseModel):
    run_id: str = Field(..., description="Run identifier matching request")
    status: SimulationStatus = Field(..., description="Simulation execution status")
    source: str = Field(..., description="'member2_simulator' or clearly labelled 'mock_simulator'")
    is_mock: bool = Field(default=False, description="Explicit boolean indicating if metrics are synthetic/mock")
    metrics: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="System-level metrics (e.g. p95_latency_ms, throughput_rps, cost_per_hour, availability)"
    )
    component_metrics: List[ComponentMetric] = Field(
        default_factory=list,
        description="Per-component fine-grained metrics from simulation"
    )
    warnings: List[str] = Field(default_factory=list, description="Simulation warnings or capacity alerts")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made by simulator engine")
    simulator_version: Optional[str] = Field(None, description="Version of Member 2 simulator engine")
    execution_mode: Optional[str] = Field(default="real", description="'real' discrete simulation or 'mock'")
    engine_name: Optional[str] = Field(default="discrete_event_engine", description="Simulator engine identifier")
    request_id: Optional[str] = Field(default=None, description="Request correlation identifier")


class DiagnosticExperimentRequest(BaseModel):
    experiment_id: str = Field(..., description="Unique experiment ID")
    baseline_run_id: str = Field(..., description="Baseline run ID this experiment builds upon")
    experiment_type: SupportedDiagnosticExperiment = Field(
        ...,
        description="Experiment type from supported allowlist"
    )
    target_components: List[str] = Field(..., description="Target component IDs under diagnostic test")
    parameters_to_change: Dict[str, Any] = Field(
        ...,
        description="Parameters to alter (e.g. {'requests_per_second': 2000} or {'db_latency_overhead_ms': 50})"
    )
    fixed_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters that must remain constant to ensure fair comparison"
    )
    reason: str = Field(..., description="Scientific rationale for running this diagnostic experiment")
    hypotheses_tested: List[str] = Field(..., description="IDs of hypotheses being evaluated")
    expected_evidence: str = Field(..., description="What distinguishing evidence is expected")


class MetricDiff(BaseModel):
    metric_name: str = Field(..., description="Name of compared metric")
    baseline_value: Optional[float] = Field(None, description="Original baseline measurement")
    diagnostic_value: Optional[float] = Field(None, description="Measurement observed during diagnostic")
    diff_value: Optional[float] = Field(None, description="Numerical difference (diagnostic - baseline)")
    diff_pct: Optional[float] = Field(None, description="Percentage change (+/- %)")
    unit: str = Field(..., description="Unit of measurement (e.g. 'ms', 'rps', '%', 'USD/hr')")
    interpretation: str = Field(..., description="Human/AI interpretation of what this change indicates")


class DiagnosticExperimentResponse(BaseModel):
    experiment_id: str = Field(..., description="Experiment identifier")
    baseline_run_id: str = Field(..., description="Original baseline run ID")
    status: SimulationStatus = Field(..., description="Experiment simulation status")
    source: str = Field(..., description="'member2_simulator' or 'mock_simulator'")
    is_mock: bool = Field(default=False, description="True if mock data")
    metrics: Dict[str, Optional[float]] = Field(default_factory=dict, description="New metrics under diagnostic conditions")
    component_metrics: List[ComponentMetric] = Field(default_factory=list, description="Per-component metrics")
    diff_from_baseline: List[MetricDiff] = Field(default_factory=list, description="Computed metric differences with units")
    warnings: List[str] = Field(default_factory=list, description="Simulation warnings")
    simulator_version: Optional[str] = Field(None, description="Simulator version")
    execution_mode: Optional[str] = Field(default="real", description="'real' discrete simulation or 'mock'")
    engine_name: Optional[str] = Field(default="discrete_event_engine", description="Simulator engine identifier")
    request_id: Optional[str] = Field(default=None, description="Request correlation identifier")


# ============================================================================
# Root-Cause Investigation Models
# ============================================================================

class EvidenceReference(BaseModel):
    run_id: str = Field(..., description="Baseline or experiment run ID")
    experiment_id: Optional[str] = Field(None, description="Diagnostic experiment ID, if from an experiment")
    metric_name: str = Field(..., description="Specific metric observed")
    observed_value: Optional[float] = Field(None, description="Observed numeric value")
    baseline_value: Optional[float] = Field(None, description="Baseline numeric value for comparison")
    diff: Optional[float] = Field(None, description="Observed delta")
    unit: str = Field(..., description="Unit of measurement")
    description: str = Field(..., description="How this data point acts as evidence")


class RootCauseHypothesis(BaseModel):
    hypothesis_id: str = Field(..., description="Unique hypothesis ID (e.g. 'HYP-001')")
    title: str = Field(..., description="Concise hypothesis summary (e.g. 'Database write contention bottleneck')")
    description: str = Field(..., description="Detailed explanation of failure mechanism")
    affected_components: List[str] = Field(..., description="Components directly involved")
    supporting_evidence: List[EvidenceReference] = Field(
        default_factory=list,
        description="Concrete evidence from simulations supporting this hypothesis"
    )
    contradicting_evidence: List[EvidenceReference] = Field(
        default_factory=list,
        description="Concrete evidence contradicting or weakening this hypothesis"
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Missing measurements that would prove or disprove this hypothesis"
    )
    confidence_label: ConfidenceLabel = Field(
        ...,
        description="Controlled confidence category: low, medium, or high (not a calibrated probability)"
    )
    recommended_experiment: Optional[SupportedDiagnosticExperiment] = Field(
        None,
        description="Recommended diagnostic experiment from allowlist to test this hypothesis"
    )
    status: HypothesisStatus = Field(
        default=HypothesisStatus.CANDIDATE,
        description="Current verification status of hypothesis"
    )


class RootCauseAnalysisResult(BaseModel):
    status: InvestigationStatus = Field(..., description="Overall status of root-cause investigation")
    hypotheses: List[RootCauseHypothesis] = Field(default_factory=list, description="Evaluated hypotheses")
    experiments: List[DiagnosticExperimentResponse] = Field(
        default_factory=list,
        description="Diagnostic experiments executed during investigation"
    )
    evidence_summary: List[str] = Field(
        default_factory=list,
        description="Key factual takeaways directly substantiated by simulation data"
    )


# ============================================================================
# Optimization Handoff Contract (Member 1 -> Member 2)
# ============================================================================

class ConfirmedFinding(BaseModel):
    finding_id: str = Field(..., description="Unique finding ID")
    title: str = Field(..., description="Title of confirmed finding")
    affected_components: List[str] = Field(..., description="Components affected")
    evidence_references: List[EvidenceReference] = Field(..., description="Traceable evidence confirming finding")
    impact_summary: str = Field(..., description="Impact on system performance or reliability")


class OptimizationHandoff(BaseModel):
    confirmed_findings: List[ConfirmedFinding] = Field(
        default_factory=list,
        description="Substantiated root causes with evidence references"
    )
    ranked_hypotheses: List[RootCauseHypothesis] = Field(
        default_factory=list,
        description="Hypotheses ordered by confidence and severity"
    )
    recommended_targets: List[str] = Field(
        default_factory=list,
        description="Component IDs Member 2 should focus on for architectural changes"
    )
    hard_constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Constraints that MUST be satisfied by Member 2 alternatives"
    )
    required_comparison_metrics: List[str] = Field(
        default_factory=lambda: [
            "p95_latency_ms",
            "throughput_rps",
            "cost_per_hour",
            "availability"
        ],
        description="Metrics Member 2 should evaluate when generating alternative designs"
    )
    assumptions_to_preserve: List[str] = Field(
        default_factory=list,
        description="Assumptions that Member 2 must keep constant for fair comparison"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Bottlenecks, risk factors, or incomplete evidence warnings"
    )


class Provenance(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str = Field(..., description="Configured LLM identifier (e.g. 'gemini-2.0-flash', 'gemma-2-27b-it')")
    simulator_version: Optional[str] = Field(None, description="Simulator version string")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO8601 timestamp"
    )
    schema_version: str = Field(default=SCHEMA_VERSION, description="Contract version")


class Member1Handoff(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION, description="Data contract version")
    investigation_id: str = Field(..., description="Unique investigation identifier")
    status: InvestigationStatus = Field(..., description="Investigation status")
    architecture: Architecture = Field(..., description="Original validated architecture")
    architecture_validation: ArchitectureValidationResult = Field(
        ...,
        description="Validation outcome, warnings, assumptions, questions"
    )
    baseline: BaselineSimulationResponse = Field(
        ...,
        description="Baseline simulation response with metrics and status"
    )
    root_cause_analysis: RootCauseAnalysisResult = Field(
        ...,
        description="Root cause investigation results, hypotheses, experiments"
    )
    optimization_handoff: OptimizationHandoff = Field(
        ...,
        description="Clean, structured directive for Member 2's optimizer"
    )
    provenance: Provenance = Field(
        ...,
        description="Audit metadata, model ID, simulator version, timestamp"
    )


# ============================================================================
# API Request & Response Models
# ============================================================================

class ArchitectureAnalyzeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    architecture_id: str
    status: str
    architecture: Optional[Architecture] = None
    validation: ArchitectureValidationResult
    direct_observations: List[str] = Field(default_factory=list)
    inferred_elements: List[str] = Field(default_factory=list)
    unknown_elements: List[str] = Field(default_factory=list)
    raw_model_response: Optional[str] = None
    model_id: Optional[str] = Field(None, description="Model identifier used for analysis or 'mock-extractor'")
    is_mock: bool = Field(default=False, description="True if analysis was performed via deterministic mock")
    execution_mode: Optional[str] = Field(default="real", description="'real' or 'mock'")
    fallback_used: Optional[bool] = Field(default=False, description="True if deterministic fallback was triggered")
    provider: Optional[str] = Field(default=None, description="AI Provider used ('gemma', 'gemini', 'deterministic_fallback')")
    request_id: Optional[str] = Field(default=None, description="Request correlation ID")


class StartInvestigationRequest(BaseModel):
    architecture: Architecture = Field(..., description="Validated architecture object")
    max_diagnostic_experiments: Optional[int] = Field(default=3, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(default=60, ge=10, le=300)


class InvestigationDetailResponse(BaseModel):
    investigation_id: str
    status: InvestigationStatus
    created_at: str
    updated_at: str
    architecture_id: str
    baseline: Optional[BaselineSimulationResponse] = None
    root_cause_analysis: Optional[RootCauseAnalysisResult] = None
    handoff_ready: bool = False
    error: Optional[str] = None
    execution_mode: Optional[str] = Field(default="real", description="'real' or 'mock'")
    engine_name: Optional[str] = Field(default="discrete_event_engine", description="Simulator engine name")
    request_id: Optional[str] = Field(default=None, description="Request correlation ID")


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
