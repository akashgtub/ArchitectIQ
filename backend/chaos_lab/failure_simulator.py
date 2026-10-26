"""Resilience and chaos engineering simulation engine for ArchitectIQ.

Injects simulated faults (API crashes, replica loss, database slowdown/outage,
cache outages, timeouts, traffic spikes) to evaluate architecture resilience,
redundancy effectiveness, and recovery behavior.
"""

from __future__ import annotations

import copy
from typing import List, Optional

from backend.simulator.engine import SimulationEngine, SimulationError
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Constraints,
    FailureScenario,
    FailureSimulationResult,
    FailureType,
    PerformanceMetrics,
    WorkloadConfig,
)


class FailureSimulator:
    """Executes controlled fault-injection simulations against system architectures."""

    def __init__(
        self,
        architecture: ArchitectureGraph,
        workload: WorkloadConfig,
        scenario: FailureScenario,
        constraints: Optional[Constraints] = None,
    ) -> None:
        self.architecture = architecture
        self.workload = workload
        self.scenario = scenario
        self.constraints = constraints
        self._validate_scenario()

    def _validate_scenario(self) -> None:
        """Validate failure scenario parameters and target component existence."""
        sc = self.scenario
        if sc.degradation_factor < 0.0:
            raise ValueError(f"Scenario degradation_factor must be non-negative, got {sc.degradation_factor}")

        if sc.start_time_sec < 0.0:
            raise ValueError(f"Scenario start_time_sec must be non-negative, got {sc.start_time_sec}")

        if sc.duration_sec is not None and sc.duration_sec <= 0.0:
            raise ValueError(f"Scenario duration_sec must be positive, got {sc.duration_sec}")

        if sc.failure_type != FailureType.TRAFFIC_SPIKE:
            if not sc.target_component_id:
                raise ValueError(
                    f"Failure scenario '{sc.name}' of type '{sc.failure_type.value}' requires a 'target_component_id'."
                )
            target = self.architecture.get_component(sc.target_component_id)
            if not target:
                raise ValueError(
                    f"Target component '{sc.target_component_id}' not found in architecture. "
                    f"Available components: {[c.id for c in self.architecture.components]}"
                )

    def _check_redundancy(self, target_comp: Optional[Component]) -> bool:
        """Determine if the architecture provides redundancy for the targeted component."""
        if not target_comp:
            return False

        # If target component itself has multiple active replicas
        if target_comp.replicas > 1:
            return True

        # If there are peer components of the same type behind a load balancer
        peers = [c for c in self.architecture.components if c.type == target_comp.type and c.id != target_comp.id]
        if peers:
            return True

        return False

    def _generate_resilience_summary(
        self,
        baseline: PerformanceMetrics,
        failure: PerformanceMetrics,
        redundancy_supported: bool,
        recovery_observed: bool,
        affected_comps: List[str],
    ) -> str:
        """Generate comprehensive diagnostic summary of resilience and failure behavior."""
        sc = self.scenario
        lat_change = failure.p95_latency_ms - baseline.p95_latency_ms
        tp_change = failure.throughput_rps - baseline.throughput_rps
        err_change = (failure.error_rate - baseline.error_rate) * 100

        lines = [
            f"Chaos Experiment: '{sc.name}' ({sc.failure_type.value})",
            f"- Affected Components: {', '.join(affected_comps)}",
            f"- p95 Latency: {baseline.p95_latency_ms:.2f} ms -> {failure.p95_latency_ms:.2f} ms ({lat_change:+.2f} ms)",
            f"- Completed Throughput: {baseline.throughput_rps:.1f} RPS -> {failure.throughput_rps:.1f} RPS ({tp_change:+.1f} RPS)",
            f"- Error Rate: {baseline.error_rate * 100:.2f}% -> {failure.error_rate * 100:.2f}% ({err_change:+.2f}%)",
            f"- Redundancy Supported: {'Yes' if redundancy_supported else 'No (Single Point of Failure)'}",
            f"- Recovery Observed: {'Yes (Traffic normalized post-fault)' if recovery_observed else 'No (Fault persisted or caused unrecovered queue saturation)'}",
        ]

        if sc.failure_type == FailureType.CACHE_OUTAGE:
            lines.append("Impact: Cache outage caused 100% cache misses, cascading high read traffic directly onto downstream database.")
        elif sc.failure_type in (FailureType.API_CRASH, FailureType.REPLICA_LOSS):
            if redundancy_supported:
                lines.append("Impact: Active peer replicas absorbed traffic without total tier failure; throughput partially degraded.")
            else:
                lines.append("Impact: CRITICAL: Target component has only 1 replica (SPOF); failure caused total service outage on this tier.")
        elif sc.failure_type in (FailureType.DB_SLOWDOWN, FailureType.LATENCY_INCREASE):
            lines.append(f"Impact: Upstream service queues accumulated significant backlog, driving p95 latency to {failure.p95_latency_ms:.2f} ms.")
        elif sc.failure_type == FailureType.TIMEOUT:
            lines.append("Impact: Requests timed out waiting on degraded dependency, driving up error rate.")
        elif sc.failure_type == FailureType.TRAFFIC_SPIKE:
            lines.append(f"Impact: Sudden {sc.degradation_factor}x traffic spike saturated component capacities, triggering queue overflows.")

        return "\n".join(lines)

    def simulate(self) -> FailureSimulationResult:
        """Run baseline and failure simulations, and compute comparative resilience metrics."""
        # 1. Baseline simulation (deep-copied to preserve original)
        base_arch = copy.deepcopy(self.architecture)
        base_workload = copy.deepcopy(self.workload)
        base_constraints = copy.deepcopy(self.constraints) if self.constraints else None

        baseline_engine = SimulationEngine(
            graph=base_arch,
            workload=base_workload,
            constraints=base_constraints,
        )
        baseline_result = baseline_engine.run()
        baseline_metrics = baseline_result.metrics

        # 2. Failure simulation
        fail_arch = copy.deepcopy(self.architecture)
        fail_workload = copy.deepcopy(self.workload)
        fail_constraints = copy.deepcopy(self.constraints) if self.constraints else None

        failure_engine = SimulationEngine(
            graph=fail_arch,
            workload=fail_workload,
            constraints=fail_constraints,
            failure_scenario=self.scenario,
        )
        failure_result = failure_engine.run()
        failure_metrics = failure_result.metrics

        # 3. Calculate deltas
        latency_delta = round(failure_metrics.p95_latency_ms - baseline_metrics.p95_latency_ms, 2)
        throughput_delta = round(failure_metrics.throughput_rps - baseline_metrics.throughput_rps, 2)
        error_rate_delta = round(failure_metrics.error_rate - baseline_metrics.error_rate, 4)

        # 4. Identify affected components
        affected_comps: List[str] = []
        if self.scenario.target_component_id:
            affected_comps.append(self.scenario.target_component_id)
            # Add downstream cascaded bottlenecks
            for c_id, m in failure_metrics.component_breakdown.items():
                if m.is_bottleneck and c_id not in affected_comps:
                    affected_comps.append(c_id)
        else:
            affected_comps = [c.id for c in self.architecture.components]

        # 5. Redundancy & Recovery
        target_comp = self.architecture.get_component(self.scenario.target_component_id) if self.scenario.target_component_id else None
        redundancy_supported = self._check_redundancy(target_comp)

        recovery_observed = False
        if self.scenario.duration_sec is not None and self.scenario.duration_sec < self.workload.duration_seconds:
            # If total failure didn't collapse the entire run and recovery mode is modeled
            if failure_metrics.completed_requests > 0:
                recovery_observed = True

        status = failure_result.status

        summary = self._generate_resilience_summary(
            baseline=baseline_metrics,
            failure=failure_metrics,
            redundancy_supported=redundancy_supported,
            recovery_observed=recovery_observed,
            affected_comps=affected_comps,
        )

        return FailureSimulationResult(
            status=status,
            scenario=self.scenario,
            affected_components=affected_comps,
            baseline_metrics=baseline_metrics,
            failure_metrics=failure_metrics,
            latency_delta_ms=latency_delta,
            throughput_delta_rps=throughput_delta,
            error_rate_delta=error_rate_delta,
            redundancy_supported=redundancy_supported,
            recovery_observed=recovery_observed,
            bottlenecks=failure_result.bottlenecks,
            resilience_summary=summary,
        )


def simulate_failure(
    architecture: ArchitectureGraph,
    workload: WorkloadConfig,
    scenario: FailureScenario,
    constraints: Optional[Constraints] = None,
) -> FailureSimulationResult:
    """Convenience functional interface to run a failure simulation."""
    sim = FailureSimulator(
        architecture=architecture,
        workload=workload,
        scenario=scenario,
        constraints=constraints,
    )
    return sim.simulate()
