"""Discrete-event and queueing simulation engine for ArchitectIQ.

Models architecture graph execution, multi-hop request routing, component concurrency,
replica scaling, cache-aside semantics (hits/misses), queue saturation, and latency accumulation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from backend.simulator.performance import (
    compile_performance_metrics,
    evaluate_constraints,
    identify_bottlenecks,
)
from backend.simulator.schemas import (
    ArchitectureGraph,
    Component,
    ComponentType,
    Connection,
    Constraints,
    PathType,
    SimulationResult,
    WorkloadConfig,
)
from backend.simulator.workload import SimulatedRequest, WorkloadGenerator


class SimulationError(Exception):
    """Raised when an architecture graph or workload configuration cannot be simulated."""
    pass


class SimulationEngine:
    """Core simulation engine executing workload-driven architecture simulations."""

    def __init__(
        self,
        graph: ArchitectureGraph,
        workload: WorkloadConfig,
        constraints: Optional[Constraints] = None,
    ) -> None:
        self.graph = graph
        self.workload = workload
        self.constraints = constraints
        self._validate_topology()

    def _validate_topology(self) -> None:
        """Validate that the graph topology can be simulated meaningfully."""
        if not self.graph.components:
            raise SimulationError("Architecture graph must contain at least one component.")

        entry_points = self.graph.get_entry_points()
        if not entry_points:
            raise SimulationError(
                "No entry-point component found in architecture graph. "
                "Ensure at least one component has no incoming connections or is a load balancer/API server."
            )

        # Check for completely disconnected components when more than 1 component exists
        if len(self.graph.components) > 1:
            sources = {c.source for c in self.graph.connections}
            targets = {c.target for c in self.graph.connections}
            isolated = [
                c.id for c in self.graph.components
                if c.id not in sources and c.id not in targets
            ]
            if isolated:
                raise SimulationError(
                    f"Isolated / unreachable components detected in graph: {sorted(isolated)}. "
                    "Every component must be connected in the architecture topology."
                )

        # Check reachability from entry points
        visited: Set[str] = set()
        queue: List[str] = [ep.id for ep in entry_points]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            for conn in self.graph.get_outgoing_connections(curr):
                if conn.target not in visited:
                    queue.append(conn.target)

        all_ids = {c.id for c in self.graph.components}
        unreachable = all_ids - visited
        if unreachable:
            raise SimulationError(
                f"Isolated / unreachable components detected in graph: {sorted(unreachable)}. "
                "Every component must be reachable from an entry point."
            )

    def _calculate_queue_wait_ms(
        self,
        component: Component,
        offered_rps: float,
        current_queue_depth: float,
        is_write: bool = False,
    ) -> float:
        """Calculate estimated queue wait time in milliseconds using M/M/c approximation.

        For databases on write requests, write capacity is constrained to the primary replica (1 replica),
        as standard single-primary replication does not scale write throughput via read replicas.
        """
        if component.type == ComponentType.DATABASE and is_write:
            replicas = 1
            eff_capacity = component.capacity_rps
        else:
            replicas = component.replicas
            eff_capacity = component.capacity_rps * replicas

        if eff_capacity <= 0:
            return 10000.0

        utilization = offered_rps / eff_capacity

        if utilization < 0.99:
            # M/M/c approximation for expected queue waiting time Wq
            # Wq ≈ (rho^sqrt(2(c+1))) / (c * mu * (1 - rho))
            rho = max(0.01, utilization)
            exponent = math.sqrt(2 * (replicas + 1))
            denominator = replicas * component.capacity_rps * max(0.01, 1.0 - rho)
            wq_sec = (rho ** exponent) / denominator
            wq_ms = wq_sec * 1000.0
            # Add dynamic queue drain time if residual queue exists
            drain_ms = (current_queue_depth / eff_capacity) * 1000.0
            return max(0.0, wq_ms + drain_ms)
        else:
            # Saturated queue: wait time is driven by queue draining
            drain_ms = (max(1.0, current_queue_depth) / eff_capacity) * 1000.0
            return max(50.0, drain_ms)

    def run(self) -> SimulationResult:
        """Execute the discrete-event simulation and return structured performance metrics."""
        workload_gen = WorkloadGenerator(self.workload)
        requests = workload_gen.generate_requests()

        # Deterministic RNG for stochastic routing & cache hits
        sim_rng = np.random.RandomState(self.workload.seed)

        # Track per-component cumulative metrics
        component_stats: Dict[str, dict] = {
            c.id: {
                "offered_count": 0,
                "completed_count": 0,
                "dropped_count": 0,
                "total_service_ms": 0.0,
                "total_queue_ms": 0.0,
                "current_queue": 0.0,
                "queue_samples": [],
            }
            for c in self.graph.components
        }

        entry_points = self.graph.get_entry_points()
        entry_point_ids = [ep.id for ep in entry_points]

        # Time tracking for queue dynamics
        duration = self.workload.duration_seconds
        step_size = self.workload.step_size_sec
        steps_count = max(1, int(math.ceil(duration / step_size)))

        # Process each simulated request
        for req in requests:
            t = req.arrival_time
            current_rate = workload_gen.get_rate_at(t)

            # Pick entry point (balanced round-robin / uniform)
            entry_id = entry_point_ids[req.request_id % len(entry_point_ids)]
            curr_component = self.graph.get_component(entry_id)
            if not curr_component:
                req.mark_dropped(entry_id, "Entry point component not found")
                continue

            accumulated_latency_ms = 0.0
            dropped = False

            # Traverse the architecture graph along outgoing connections
            while curr_component is not None:
                c_id = curr_component.id
                stats = component_stats[c_id]
                stats["offered_count"] += 1

                if curr_component.type == ComponentType.DATABASE and not req.is_read:
                    eff_capacity = curr_component.capacity_rps
                else:
                    eff_capacity = curr_component.capacity_rps * curr_component.replicas

                # Check queue overflow
                if stats["current_queue"] >= curr_component.max_queue_size:
                    stats["dropped_count"] += 1
                    req.mark_dropped(c_id, f"Queue overflow at {c_id} (max {curr_component.max_queue_size})")
                    dropped = True
                    break

                # Calculate service time & queue delay
                svc_time = curr_component.base_latency_ms
                # Add slight write overhead for database persistence (1.25x base)
                if curr_component.type == ComponentType.DATABASE and not req.is_read:
                    svc_time *= 1.25

                # Estimate queue wait time
                queue_wait = self._calculate_queue_wait_ms(
                    curr_component,
                    current_rate,
                    stats["current_queue"],
                    is_write=(not req.is_read),
                )

                hop_latency = svc_time + queue_wait
                req.hop_latencies[c_id] = hop_latency
                accumulated_latency_ms += hop_latency

                stats["completed_count"] += 1
                stats["total_service_ms"] += svc_time
                stats["total_queue_ms"] += queue_wait

                # Update queue level with stochastic arrivals & service drain
                if current_rate > eff_capacity:
                    stats["current_queue"] = min(
                        curr_component.max_queue_size,
                        stats["current_queue"] + (current_rate - eff_capacity) / max(1, eff_capacity),
                    )
                else:
                    stats["current_queue"] = max(0.0, stats["current_queue"] - 0.2)

                stats["queue_samples"].append(stats["current_queue"])

                # Handle Cache Semantics
                if curr_component.type == ComponentType.CACHE and req.is_read:
                    hit_ratio = curr_component.cache_hit_ratio or 0.8
                    is_hit = sim_rng.random_sample() < hit_ratio
                    if is_hit:
                        # Cache hit: request completes at cache, skips downstream database
                        break

                # Determine next hop along connections
                outgoing = self.graph.get_outgoing_connections(c_id)
                if not outgoing:
                    # Leaf node reached (e.g. database or external service)
                    break

                # Filter connections by path_type (read vs write)
                eligible_conns: List[Connection] = []
                for conn in outgoing:
                    if req.is_read and conn.path_type in (PathType.READ, PathType.BOTH):
                        eligible_conns.append(conn)
                    elif (not req.is_read) and conn.path_type in (PathType.WRITE, PathType.BOTH):
                        eligible_conns.append(conn)

                if not eligible_conns:
                    # No matching path for this traffic type
                    break

                # Select connection (balanced across downstream targets)
                selected_conn = eligible_conns[req.request_id % len(eligible_conns)]
                accumulated_latency_ms += selected_conn.latency_overhead_ms

                curr_component = self.graph.get_component(selected_conn.target)

            if not dropped:
                req.mark_completed(accumulated_latency_ms)

        # Compute summary queue depths
        for c_id, stats in component_stats.items():
            samples = stats.pop("queue_samples", [])
            stats["mean_queue_depth"] = float(np.mean(samples)) if samples else 0.0

        # Compile performance metrics
        metrics = compile_performance_metrics(
            requests=requests,
            duration_seconds=self.workload.duration_seconds,
            graph=self.graph,
            component_stats=component_stats,
        )

        # Diagnose bottlenecks and evaluate constraints
        bottlenecks = identify_bottlenecks(metrics.component_breakdown)
        violations = evaluate_constraints(metrics, self.constraints)

        status = "success"
        if violations or metrics.error_rate > 0.05:
            status = "degraded"
        if metrics.error_rate > 0.50 or metrics.completed_requests == 0:
            status = "failed"

        assumptions = [
            "Cache-aside pattern: read traffic queries cache first with probability 'cache_hit_ratio' completing at cache; cache misses and write traffic route to downstream database.",
            "Replica scaling: total component throughput capacity equals single-replica capacity multiplied by replica count (capacity_rps * replicas).",
            "Routing: incoming traffic is uniformly distributed across available downstream replicas and eligible connections.",
            "Queueing model: M/M/c queueing approximation applied for wait times below saturation; requests exceeding max_queue_size are dropped.",
            "Network overhead: per-hop transmission and serialization latency applied from connection definitions.",
        ]

        metadata = {
            "method": "discrete_event_queueing",
            "seed": self.workload.seed,
            "total_simulated_requests": len(requests),
            "duration_seconds": self.workload.duration_seconds,
            "pattern": self.workload.pattern.value,
        }

        return SimulationResult(
            status=status,
            simulation_type="baseline",
            metrics=metrics,
            bottlenecks=bottlenecks,
            constraint_violations=violations,
            assumptions=assumptions,
            simulation_metadata=metadata,
        )
