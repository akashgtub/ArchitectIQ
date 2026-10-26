"""Performance analytics and bottleneck detection for ArchitectIQ.

Computes latency distributions (p50, p95, p99), throughput, error rates,
component queueing metrics, infrastructure cost, and constraint violations from simulation observations.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np

from backend.simulator.schemas import (
    ArchitectureGraph,
    BottleneckInfo,
    ComponentMetrics,
    Constraints,
    ConstraintViolation,
    PerformanceMetrics,
    SeverityLevel,
)
from backend.simulator.workload import SimulatedRequest


def calculate_latencies(
    latencies: List[float],
) -> tuple[float, float, float, float]:
    """Calculate mean, p50, p95, and p99 from a sample of observed request latencies.

    Returns:
        (mean_latency_ms, p50_latency_ms, p95_latency_ms, p99_latency_ms)
        Returns (0.0, 0.0, 0.0, 0.0) if no samples exist.
    """
    if not latencies:
        return 0.0, 0.0, 0.0, 0.0

    arr = np.array(latencies, dtype=np.float64)
    mean_val = float(np.mean(arr))
    p50_val = float(np.percentile(arr, 50))
    p95_val = float(np.percentile(arr, 95))
    p99_val = float(np.percentile(arr, 99))

    return (
        round(mean_val, 2),
        round(p50_val, 2),
        round(p95_val, 2),
        round(p99_val, 2),
    )


def calculate_component_cost(graph: ArchitectureGraph) -> float:
    """Calculate the estimated total monthly infrastructure cost in USD."""
    total = 0.0
    for comp in graph.components:
        total += comp.replicas * comp.cost_per_month_usd
    return round(total, 2)


def evaluate_constraints(
    metrics: PerformanceMetrics,
    constraints: Optional[Constraints],
) -> List[ConstraintViolation]:
    """Check performance metrics against user-defined hard constraints."""
    violations: List[ConstraintViolation] = []
    if not constraints:
        return violations

    # 1. Max p95 latency
    if constraints.max_p95_latency_ms is not None:
        if metrics.p95_latency_ms > constraints.max_p95_latency_ms:
            violations.append(
                ConstraintViolation(
                    constraint_name="max_p95_latency_ms",
                    threshold=constraints.max_p95_latency_ms,
                    actual_value=metrics.p95_latency_ms,
                    message=(
                        f"p95 latency ({metrics.p95_latency_ms:.2f} ms) exceeds limit "
                        f"({constraints.max_p95_latency_ms:.2f} ms)"
                    ),
                )
            )

    # 2. Max p99 latency
    if constraints.max_p99_latency_ms is not None:
        if metrics.p99_latency_ms > constraints.max_p99_latency_ms:
            violations.append(
                ConstraintViolation(
                    constraint_name="max_p99_latency_ms",
                    threshold=constraints.max_p99_latency_ms,
                    actual_value=metrics.p99_latency_ms,
                    message=(
                        f"p99 latency ({metrics.p99_latency_ms:.2f} ms) exceeds limit "
                        f"({constraints.max_p99_latency_ms:.2f} ms)"
                    ),
                )
            )

    # 3. Monthly budget
    if constraints.monthly_budget_usd is not None:
        if metrics.total_monthly_cost_usd > constraints.monthly_budget_usd:
            violations.append(
                ConstraintViolation(
                    constraint_name="monthly_budget_usd",
                    threshold=constraints.monthly_budget_usd,
                    actual_value=metrics.total_monthly_cost_usd,
                    message=(
                        f"Estimated monthly cost (${metrics.total_monthly_cost_usd:.2f}) exceeds budget "
                        f"(${constraints.monthly_budget_usd:.2f})"
                    ),
                )
            )

    # 4. Min throughput
    if constraints.min_throughput_rps is not None:
        if metrics.throughput_rps < constraints.min_throughput_rps:
            violations.append(
                ConstraintViolation(
                    constraint_name="min_throughput_rps",
                    threshold=constraints.min_throughput_rps,
                    actual_value=metrics.throughput_rps,
                    message=(
                        f"Throughput ({metrics.throughput_rps:.2f} RPS) is below required minimum "
                        f"({constraints.min_throughput_rps:.2f} RPS)"
                    ),
                )
            )

    # 5. Max error rate
    if constraints.max_error_rate is not None:
        if metrics.error_rate > constraints.max_error_rate:
            violations.append(
                ConstraintViolation(
                    constraint_name="max_error_rate",
                    threshold=constraints.max_error_rate,
                    actual_value=metrics.error_rate,
                    message=(
                        f"Error rate ({metrics.error_rate * 100:.2f}%) exceeds maximum limit "
                        f"({constraints.max_error_rate * 100:.2f}%)"
                    ),
                )
            )

    return violations


def identify_bottlenecks(
    component_metrics: Dict[str, ComponentMetrics],
) -> List[BottleneckInfo]:
    """Diagnose bottlenecks from per-component queueing and utilization observations."""
    bottlenecks: List[BottleneckInfo] = []

    for comp_id, m in component_metrics.items():
        if m.utilization >= 0.80 or m.dropped_rps > 0 or m.mean_queue_depth > 10.0:
            # Determine severity
            if m.utilization >= 1.0 or m.dropped_rps > 0:
                severity = SeverityLevel.CRITICAL
                reason = (
                    f"Component '{comp_id}' ({m.component_type.value}) is saturated at {m.utilization * 100:.1f}% "
                    f"utilization. Offered load ({m.offered_rps:.1f} RPS) exceeds effective capacity "
                    f"({m.effective_capacity_rps:.1f} RPS) resulting in {m.dropped_rps:.1f} dropped RPS."
                )
                action = (
                    f"Scale '{comp_id}' replicas from {m.replicas} to {int(np.ceil(m.offered_rps / (m.effective_capacity_rps / m.replicas)))} "
                    f"or increase single-replica capacity."
                )
            elif m.utilization >= 0.90:
                severity = SeverityLevel.HIGH
                reason = (
                    f"Component '{comp_id}' is operating near capacity threshold ({m.utilization * 100:.1f}% "
                    f"utilization) with significant queue buildup (avg queue depth: {m.mean_queue_depth:.1f})."
                )
                action = f"Add replica to '{comp_id}' (current: {m.replicas}) to provide headroom for traffic bursts."
            else:
                severity = SeverityLevel.MEDIUM
                reason = (
                    f"Component '{comp_id}' utilization is elevated at {m.utilization * 100:.1f}%. "
                    f"Mean queue time: {m.mean_queue_time_ms:.2f} ms."
                )
                action = f"Monitor '{comp_id}' performance; consider horizontal scaling if traffic increases."

            bottlenecks.append(
                BottleneckInfo(
                    component_id=comp_id,
                    severity=severity,
                    reason=reason,
                    utilization=round(m.utilization, 3),
                    recommended_action=action,
                )
            )

    # Sort bottlenecks by utilization descending
    bottlenecks.sort(key=lambda b: b.utilization, reverse=True)
    return bottlenecks


def compile_performance_metrics(
    requests: List[SimulatedRequest],
    duration_seconds: float,
    graph: ArchitectureGraph,
    component_stats: Dict[str, dict],
) -> PerformanceMetrics:
    """Compile end-to-end performance metrics from discrete simulated request events."""
    duration = max(0.001, duration_seconds)
    total_requests = len(requests)
    completed_requests = sum(1 for r in requests if r.completed)
    dropped_requests = sum(1 for r in requests if r.dropped)

    # Completed latencies
    completed_latencies = [r.total_latency_ms for r in requests if r.completed]
    mean_lat, p50_lat, p95_lat, p99_lat = calculate_latencies(completed_latencies)

    throughput = round(completed_requests / duration, 2)
    error_rate = round(dropped_requests / total_requests, 4) if total_requests > 0 else 0.0
    total_cost = calculate_component_cost(graph)

    # Compile per-component metrics
    comp_breakdown: Dict[str, ComponentMetrics] = {}
    for comp in graph.components:
        stats = component_stats.get(
            comp.id,
            {
                "offered_count": 0,
                "completed_count": 0,
                "dropped_count": 0,
                "total_service_ms": 0.0,
                "total_queue_ms": 0.0,
                "max_queue_depth": 0.0,
                "mean_queue_depth": 0.0,
            },
        )

        eff_capacity = comp.capacity_rps * comp.replicas
        offered_rps = round(stats["offered_count"] / duration, 2)
        comp_throughput = round(stats["completed_count"] / duration, 2)
        dropped_rps = round(stats["dropped_count"] / duration, 2)
        utilization = round(offered_rps / eff_capacity, 4) if eff_capacity > 0 else 1.0

        n_processed = max(1, stats["completed_count"])
        mean_svc = round(stats["total_service_ms"] / n_processed, 2) if stats["completed_count"] > 0 else comp.base_latency_ms
        mean_q = round(stats["total_queue_ms"] / n_processed, 2) if stats["completed_count"] > 0 else 0.0

        is_bottleneck = utilization >= 0.85 or dropped_rps > 0

        comp_breakdown[comp.id] = ComponentMetrics(
            component_id=comp.id,
            component_type=comp.type,
            replicas=comp.replicas,
            effective_capacity_rps=eff_capacity,
            offered_rps=offered_rps,
            throughput_rps=comp_throughput,
            dropped_rps=dropped_rps,
            utilization=utilization,
            mean_queue_depth=round(stats["mean_queue_depth"], 2),
            mean_service_time_ms=mean_svc,
            mean_queue_time_ms=mean_q,
            total_latency_ms=round(mean_svc + mean_q, 2),
            is_bottleneck=is_bottleneck,
            cost_per_month_usd=round(comp.replicas * comp.cost_per_month_usd, 2),
        )

    return PerformanceMetrics(
        mean_latency_ms=mean_lat,
        p50_latency_ms=p50_lat,
        p95_latency_ms=p95_lat,
        p99_latency_ms=p99_lat,
        throughput_rps=throughput,
        error_rate=error_rate,
        completed_requests=completed_requests,
        dropped_requests=dropped_requests,
        total_monthly_cost_usd=total_cost,
        component_breakdown=comp_breakdown,
    )
