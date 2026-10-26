"""
ArchPilot AI - Schema and Simulation Adapter
Bridges Member 1 canonical schemas (backend.shared.schemas) with
Member 2 discrete-event simulation engine (backend.simulator.schemas and backend.simulator.engine).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from backend.shared.schemas import (
    Architecture as M1Architecture,
    BaselineSimulationResponse as M1BaselineResponse,
    Component as M1Component,
    ComponentMetric as M1ComponentMetric,
    ComponentType as M1ComponentType,
    ConnectionType as M1ConnectionType,
    Constraints as M1Constraints,
    DiagnosticExperimentRequest as M1DiagRequest,
    DiagnosticExperimentResponse as M1DiagResponse,
    MetricDiff,
    SimulationStatus as M1SimStatus,
    SupportedDiagnosticExperiment,
    Workload as M1Workload,
)
from backend.api.service import run_simulation
from backend.simulator.schemas import (
    ArchitectureGraph as M2ArchitectureGraph,
    Component as M2Component,
    ComponentType as M2ComponentType,
    Connection as M2Connection,
    Constraints as M2Constraints,
    PathType as M2PathType,
    SimulationResult as M2SimulationResult,
    WorkloadConfig as M2WorkloadConfig,
    WorkloadPattern as M2WorkloadPattern,
)


def m1_component_type_to_m2(c_type: M1ComponentType) -> M2ComponentType:
    """Map Member 1 ComponentType to Member 2 ComponentType."""
    mapping = {
        M1ComponentType.API_SERVER: M2ComponentType.API_SERVER,
        M1ComponentType.WEB_SERVER: M2ComponentType.API_SERVER,
        M1ComponentType.LOAD_BALANCER: M2ComponentType.LOAD_BALANCER,
        M1ComponentType.DATABASE: M2ComponentType.DATABASE,
        M1ComponentType.CACHE: M2ComponentType.CACHE,
        M1ComponentType.MESSAGE_QUEUE: M2ComponentType.QUEUE,
        M1ComponentType.OBJECT_STORAGE: M2ComponentType.STORAGE,
        M1ComponentType.MICROSERVICE: M2ComponentType.API_SERVER,
        M1ComponentType.GATEWAY: M2ComponentType.LOAD_BALANCER,
        M1ComponentType.WORKER: M2ComponentType.API_SERVER,
        M1ComponentType.CDN: M2ComponentType.CACHE,
        M1ComponentType.EXTERNAL_SERVICE: M2ComponentType.THIRD_PARTY_SERVICE,
        M1ComponentType.UNKNOWN: M2ComponentType.API_SERVER,
    }
    return mapping.get(c_type, M2ComponentType.API_SERVER)


def adapt_m1_architecture_to_m2(arch: M1Architecture) -> tuple[M2ArchitectureGraph, M2WorkloadConfig, Optional[M2Constraints]]:
    """
    Translates Member 1 Architecture, Workload, and Constraints into Member 2
    ArchitectureGraph, WorkloadConfig, and Constraints.
    """
    m2_components: List[M2Component] = []
    for comp in arch.components:
        c_type = m1_component_type_to_m2(comp.type)
        attrs = comp.attributes or {}

        # Default capacities and latency based on component type and attributes
        cores = float(attrs.get("cpu_cores", 2.0))
        default_capacity = 1000.0
        default_latency = 15.0
        default_cost = 40.0

        if c_type == M2ComponentType.LOAD_BALANCER:
            default_capacity = 5000.0
            default_latency = 2.0
            default_cost = 25.0
        elif c_type == M2ComponentType.DATABASE:
            default_capacity = cores * 400.0
            default_latency = 25.0
            default_cost = 120.0
        elif c_type == M2ComponentType.CACHE:
            default_capacity = 10000.0
            default_latency = 1.5
            default_cost = 60.0
        elif c_type == M2ComponentType.QUEUE or c_type == M2ComponentType.MESSAGE_BROKER:
            default_capacity = 5000.0
            default_latency = 5.0
            default_cost = 30.0
        elif c_type == M2ComponentType.API_SERVER:
            default_capacity = cores * 500.0
            default_latency = 15.0
            default_cost = 40.0
        elif c_type == M2ComponentType.STORAGE:
            default_capacity = 2000.0
            default_latency = 20.0
            default_cost = 15.0
        elif c_type == M2ComponentType.THIRD_PARTY_SERVICE:
            default_capacity = 1500.0
            default_latency = 30.0
            default_cost = 20.0

        capacity_rps = float(attrs.get("capacity_rps", default_capacity))
        replicas = int(attrs.get("replicas", attrs.get("instances", 1)))
        base_latency_ms = float(attrs.get("base_latency_ms", default_latency))
        cost_per_month_usd = float(attrs.get("cost_per_month_usd", default_cost * replicas))
        cache_hit_ratio = float(attrs.get("cache_hit_ratio", 0.8)) if c_type == M2ComponentType.CACHE else None

        m2_components.append(
            M2Component(
                id=comp.id,
                type=c_type,
                name=comp.name,
                capacity_rps=max(1.0, capacity_rps),
                replicas=max(1, replicas),
                base_latency_ms=base_latency_ms,
                cost_per_month_usd=cost_per_month_usd,
                cache_hit_ratio=cache_hit_ratio,
            )
        )

    m2_connections: List[M2Connection] = []
    for conn in arch.connections:
        attrs = conn.attributes or {}
        path_type = M2PathType.BOTH
        if conn.type == M1ConnectionType.DATA_ACCESS:
            path_type = M2PathType.BOTH
        m2_connections.append(
            M2Connection(
                source=conn.source,
                target=conn.target,
                protocol=str(attrs.get("protocol", "http")),
                latency_overhead_ms=float(attrs.get("latency_overhead_ms", 1.0)),
                path_type=path_type,
            )
        )

    m2_graph = M2ArchitectureGraph(
        components=m2_components,
        connections=m2_connections,
    )

    workload = arch.workload
    m2_workload = M2WorkloadConfig(
        requests_per_second=max(1.0, workload.requests_per_second),
        read_ratio=workload.read_ratio,
        duration_seconds=10.0,
        pattern=M2WorkloadPattern.CONSTANT,
        burst_multiplier=workload.peak_multiplier or 2.0,
    )

    m2_constraints = None
    if arch.constraints:
        c = arch.constraints
        m2_constraints = M2Constraints(
            max_p95_latency_ms=c.max_p95_latency_ms,
            min_throughput_rps=c.min_throughput_rps,
            monthly_budget_usd=c.max_cost_per_hour * 730.0 if c.max_cost_per_hour else None,
        )

    return m2_graph, m2_workload, m2_constraints


def adapt_m2_simulation_to_m1_baseline(
    run_id: str,
    sim_result: M2SimulationResult,
    original_arch: M1Architecture,
) -> M1BaselineResponse:
    """
    Translates Member 2 SimulationResult into Member 1 BaselineSimulationResponse.
    """
    cost_per_hour = round(sim_result.metrics.total_monthly_cost_usd / 730.0, 2)
    availability = round(1.0 - sim_result.metrics.error_rate, 4)

    component_metrics: List[M1ComponentMetric] = []
    for comp_id, cm in sim_result.metrics.component_breakdown.items():
        component_metrics.append(
            M1ComponentMetric(
                component_id=comp_id,
                cpu_utilization_pct=round(min(100.0, cm.utilization * 100.0), 1),
                memory_utilization_pct=50.0,
                latency_p95_ms=round(cm.total_latency_ms, 2),
                throughput_rps=round(cm.throughput_rps, 1),
                error_rate_pct=round((cm.dropped_rps / max(1.0, cm.offered_rps)) * 100.0, 1) if cm.offered_rps > 0 else 0.0,
            )
        )

    warnings: List[str] = [b.reason for b in sim_result.bottlenecks]

    return M1BaselineResponse(
        run_id=run_id,
        status=M1SimStatus.COMPLETED,
        source="member2_simulator",
        is_mock=False,
        metrics={
            "p95_latency_ms": round(sim_result.metrics.p95_latency_ms, 2),
            "throughput_rps": round(sim_result.metrics.throughput_rps, 1),
            "cost_per_hour": cost_per_hour,
            "availability": availability,
        },
        component_metrics=component_metrics,
        warnings=warnings,
        assumptions=sim_result.assumptions,
        simulator_version="sim-v2.1.0",
        execution_mode="real",
        engine_name="discrete_event_engine",
    )


def run_adapted_diagnostic_experiment(
    request: M1DiagRequest,
    baseline: M1BaselineResponse,
    architecture: M1Architecture,
) -> M1DiagResponse:
    """
    Executes a real diagnostic experiment using Member 2 SimulationEngine and produces MetricDiffs.
    """
    arch_copy = copy.deepcopy(architecture)
    m2_graph, m2_workload, m2_constraints = adapt_m1_architecture_to_m2(arch_copy)

    exp_type = request.experiment_type
    params = request.parameters_to_change

    if exp_type == SupportedDiagnosticExperiment.INCREASE_WORKLOAD:
        mult = float(params.get("multiplier", 1.5))
        m2_workload.requests_per_second *= mult

    elif exp_type == SupportedDiagnosticExperiment.VARY_READ_WRITE_MIX:
        new_w = float(params.get("write_ratio", 0.5))
        m2_workload.read_ratio = max(0.0, 1.0 - new_w)

    elif exp_type == SupportedDiagnosticExperiment.SIMULATE_DB_LATENCY:
        added_latency = float(params.get("db_latency_overhead_ms", 50.0))
        for c in m2_graph.components:
            if c.id in request.target_components or c.type == M2ComponentType.DATABASE:
                c.base_latency_ms += added_latency

    elif exp_type == SupportedDiagnosticExperiment.SCALE_COMPONENT:
        new_replicas = int(params.get("replicas", 2))
        for c in m2_graph.components:
            if c.id in request.target_components:
                c.replicas = new_replicas

    elif exp_type == SupportedDiagnosticExperiment.TOGGLE_CACHE:
        enabled = bool(params.get("enabled", False))
        if not enabled:
            for c in m2_graph.components:
                if c.type == M2ComponentType.CACHE:
                    c.cache_hit_ratio = 0.0

    sim_result = run_simulation(
        architecture=m2_graph,
        workload=m2_workload,
        constraints=m2_constraints,
    )

    diag_p95 = round(sim_result.metrics.p95_latency_ms, 2)
    diag_rps = round(sim_result.metrics.throughput_rps, 1)
    diag_cost = round(sim_result.metrics.total_monthly_cost_usd / 730.0, 2)
    diag_avail = round(1.0 - sim_result.metrics.error_rate, 4)

    diag_metrics = {
        "p95_latency_ms": diag_p95,
        "throughput_rps": diag_rps,
        "cost_per_hour": diag_cost,
        "availability": diag_avail,
    }

    base_p95 = baseline.metrics.get("p95_latency_ms") or 100.0
    base_rps = baseline.metrics.get("throughput_rps") or 1000.0

    diffs: List[MetricDiff] = []

    def safe_pct(diff_val: float, base_val: float) -> Optional[float]:
        return round((diff_val / base_val) * 100.0, 1) if base_val != 0.0 else None

    p95_delta = round(diag_p95 - base_p95, 2)
    diffs.append(
        MetricDiff(
            metric_name="p95_latency_ms",
            baseline_value=base_p95,
            diagnostic_value=diag_p95,
            diff_value=p95_delta,
            diff_pct=safe_pct(p95_delta, base_p95),
            unit="ms",
            interpretation=f"Diagnostic experiment altered p95 latency by {p95_delta:+.1f}ms under {exp_type.value}.",
        )
    )

    rps_delta = round(diag_rps - base_rps, 1)
    diffs.append(
        MetricDiff(
            metric_name="throughput_rps",
            baseline_value=base_rps,
            diagnostic_value=diag_rps,
            diff_value=rps_delta,
            diff_pct=safe_pct(rps_delta, base_rps),
            unit="rps",
            interpretation=f"Throughput shifted by {rps_delta:+.1f} RPS.",
        )
    )

    component_metrics: List[M1ComponentMetric] = []
    for comp_id, cm in sim_result.metrics.component_breakdown.items():
        component_metrics.append(
            M1ComponentMetric(
                component_id=comp_id,
                cpu_utilization_pct=round(min(100.0, cm.utilization * 100.0), 1),
                memory_utilization_pct=50.0,
                latency_p95_ms=round(cm.total_latency_ms, 2),
                throughput_rps=round(cm.throughput_rps, 1),
                error_rate_pct=round((cm.dropped_rps / max(1.0, cm.offered_rps)) * 100.0, 1) if cm.offered_rps > 0 else 0.0,
            )
        )

    warnings = [b.reason for b in sim_result.bottlenecks]

    return M1DiagResponse(
        experiment_id=request.experiment_id,
        baseline_run_id=request.baseline_run_id,
        status=M1SimStatus.COMPLETED,
        source="member2_simulator",
        is_mock=False,
        metrics=diag_metrics,
        component_metrics=component_metrics,
        diff_from_baseline=diffs,
        warnings=warnings,
        simulator_version="sim-v2.1.0",
        execution_mode="real",
        engine_name="discrete_event_engine",
    )
