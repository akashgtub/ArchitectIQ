"""Architecture optimization and candidate ranking engine for ArchitectIQ.

Generates bounded, valid alternative architecture graphs, simulates each alternative
under identical workload conditions, enforces hard constraints, and ranks candidates
according to user-specified objectives (latency, cost, throughput, balanced).
"""

from __future__ import annotations

import copy
from typing import List, Optional, Tuple
import numpy as np

from backend.simulator.engine import SimulationEngine
from backend.simulator.schemas import (
    ArchitectureGraph,
    CandidateArchitecture,
    Component,
    ComponentType,
    Connection,
    Constraints,
    OptimizationObjective,
    OptimizationRequest,
    OptimizationResult,
    PathType,
    PerformanceMetrics,
    WorkloadConfig,
)


def _graph_signature(graph: ArchitectureGraph) -> str:
    """Generate canonical signature string for an architecture graph to prevent duplicate candidates."""
    comp_sigs = sorted(
        f"{c.id}:{c.type.value}:{c.capacity_rps:.1f}:{c.replicas}:{c.base_latency_ms:.1f}:{c.cost_per_month_usd:.2f}:{c.cache_hit_ratio or 0.0:.2f}"
        for c in graph.components
    )
    conn_sigs = sorted(
        f"{conn.source}->{conn.target}:{conn.protocol or 'http'}:{conn.latency_overhead_ms:.2f}:{conn.path_type.value}"
        for conn in graph.connections
    )
    return ";".join(comp_sigs) + "|" + ";".join(conn_sigs)


class ArchitectureOptimizer:
    """Explores, simulates, and ranks candidate architecture variations against baseline."""

    def __init__(
        self,
        architecture: ArchitectureGraph,
        workload: WorkloadConfig,
        constraints: Optional[Constraints] = None,
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
        max_candidates: int = 8,
    ) -> None:
        self.baseline_architecture = architecture
        self.workload = workload
        self.constraints = constraints
        self.objective = objective
        self.max_candidates = max(1, min(50, max_candidates))

    def _generate_candidate_graphs(self) -> List[Tuple[str, List[str], ArchitectureGraph]]:
        """Generate a bounded set of valid alternative architecture graphs prioritized by objective.

        Returns list of tuples: (candidate_id, modifications_list, modified_graph)
        """
        cost_candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []
        latency_candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []
        throughput_candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []
        balanced_candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []

        base = self.baseline_architecture
        base_sig = _graph_signature(base)

        api_comps = [c for c in base.components if c.type in (ComponentType.API_SERVER, ComponentType.LOAD_BALANCER)]
        db_comps = [c for c in base.components if c.type in (ComponentType.DATABASE, ComponentType.STORAGE)]
        cache_comps = [c for c in base.components if c.type == ComponentType.CACHE]

        # ---------------------------------------------------------------------
        # 1. Cost-Reduction Mutations (Rightsizing & Downscaling)
        # ---------------------------------------------------------------------
        # A. Replica downscaling for over-provisioned components
        for comp in base.components:
            if comp.replicas > 1:
                down_comps = copy.deepcopy(base.components)
                for c in down_comps:
                    if c.id == comp.id:
                        c.replicas -= 1
                cand_graph = ArchitectureGraph(
                    components=down_comps,
                    connections=copy.deepcopy(base.connections),
                )
                cost_candidates.append((
                    f"downscale-{comp.id}-replicas",
                    [f"Downscaled '{comp.id}' replicas from {comp.replicas} to {comp.replicas - 1} (-${comp.cost_per_month_usd:.2f}/mo)"],
                    cand_graph,
                ))

        # Minimal replica increment (+1) for bottlenecked architectures to achieve feasibility at lowest incremental cost
        for api in api_comps:
            c1_comps = copy.deepcopy(base.components)
            for c in c1_comps:
                if c.id == api.id:
                    c.replicas += 1
            cand1_graph = ArchitectureGraph(
                components=c1_comps,
                connections=copy.deepcopy(base.connections),
            )
            cost_candidates.append((
                f"scale-{api.id}-plus-1",
                [f"Scaled '{api.id}' replicas from {api.replicas} to {api.replicas + 1} (minimal incremental cost +${api.cost_per_month_usd:.2f}/mo)"],
                cand1_graph,
            ))

        # B. Vertical tier rightsizing (downsizing capacity by 25% for 25% cost reduction)
        for comp in base.components:
            if comp.cost_per_month_usd >= 30.0 and comp.capacity_rps >= 200.0:
                down_tier_comps = copy.deepcopy(base.components)
                new_cap = max(50.0, round(comp.capacity_rps * 0.75, 1))
                new_cost = max(10.0, round(comp.cost_per_month_usd * 0.75, 2))
                for c in down_tier_comps:
                    if c.id == comp.id:
                        c.capacity_rps = new_cap
                        c.cost_per_month_usd = new_cost
                cand_graph = ArchitectureGraph(
                    components=down_tier_comps,
                    connections=copy.deepcopy(base.connections),
                )
                cost_candidates.append((
                    f"downscale-{comp.id}-tier",
                    [f"Rightsized '{comp.id}' tier: capacity {comp.capacity_rps} -> {new_cap} RPS, cost ${comp.cost_per_month_usd:.2f} -> ${new_cost:.2f}/mo"],
                    cand_graph,
                ))

        # C. Cache-assisted DB offload (Tuning cache hit ratio while rightsizing DB)
        if cache_comps and db_comps:
            cache = cache_comps[0]
            db = db_comps[0]
            curr_hit = cache.cache_hit_ratio or 0.8
            offload_comps = copy.deepcopy(base.components)
            db_mod_desc = ""
            for c in offload_comps:
                if c.id == cache.id:
                    c.cache_hit_ratio = min(0.98, round(curr_hit + 0.15, 2))
                elif c.id == db.id:
                    if c.replicas > 1:
                        c.replicas -= 1
                        db_mod_desc = f"reduced '{db.id}' replicas to {c.replicas}"
                    else:
                        c.cost_per_month_usd = round(c.cost_per_month_usd * 0.75, 2)
                        c.capacity_rps = round(c.capacity_rps * 0.80, 1)
                        db_mod_desc = f"rightsized '{db.id}' tier to ${c.cost_per_month_usd:.2f}/mo"
            cand_graph = ArchitectureGraph(
                components=offload_comps,
                connections=copy.deepcopy(base.connections),
            )
            cost_candidates.append((
                f"cache-offload-{db.id}-downscale",
                [
                    f"Tuned '{cache.id}' hit ratio to {min(0.98, round(curr_hit + 0.15, 2)) * 100:.0f}%",
                    f"Cost-reduced database: {db_mod_desc}",
                ],
                cand_graph,
            ))

        # ---------------------------------------------------------------------
        # 2. Latency-Reduction Mutations
        # ---------------------------------------------------------------------
        # A. Database SSD / Provisioned IOPS Tier Upgrade (faster base latency + higher capacity)
        for db in db_comps:
            db_up_comps = copy.deepcopy(base.components)
            new_cap = round(db.capacity_rps * 1.5, 1)
            new_cost = round(db.cost_per_month_usd * 1.4, 2)
            new_base_lat = max(1.0, round(db.base_latency_ms * 0.75, 1))
            for c in db_up_comps:
                if c.id == db.id:
                    c.capacity_rps = new_cap
                    c.cost_per_month_usd = new_cost
                    c.base_latency_ms = new_base_lat
            cand_graph = ArchitectureGraph(
                components=db_up_comps,
                connections=copy.deepcopy(base.connections),
            )
            latency_candidates.append((
                f"upgrade-{db.id}-tier",
                [
                    f"Upgraded '{db.id}' to provisioned IOPS tier: base latency {db.base_latency_ms} -> {new_base_lat} ms, "
                    f"capacity {db.capacity_rps} -> {new_cap} RPS (${new_cost:.2f}/mo)"
                ],
                cand_graph,
            ))

        # B. Transport Protocol Optimization (gRPC transport overhead reduction to 0.2ms)
        conns_grpc = copy.deepcopy(base.connections)
        has_reducible_conn = any(c.latency_overhead_ms > 0.3 for c in conns_grpc)
        if has_reducible_conn:
            for conn in conns_grpc:
                conn.protocol = "grpc"
                conn.latency_overhead_ms = 0.2
            cand_graph = ArchitectureGraph(
                components=copy.deepcopy(base.components),
                connections=conns_grpc,
            )
            latency_candidates.append((
                "optimize-transport-protocol-grpc",
                ["Upgraded internal communication links to gRPC (reduced transport overhead to 0.2ms)"],
                cand_graph,
            ))

        # C. Cache Hit Ratio Tuning (Index pre-warming / TTL boost)
        if cache_comps:
            for cache in cache_comps:
                curr_hit = cache.cache_hit_ratio or 0.8
                if curr_hit < 0.95:
                    tuned_hit = min(0.95, round(curr_hit + 0.10, 2))
                    cache_tune_comps = copy.deepcopy(base.components)
                    for c in cache_tune_comps:
                        if c.id == cache.id:
                            c.cache_hit_ratio = tuned_hit
                    cand_graph = ArchitectureGraph(
                        components=cache_tune_comps,
                        connections=copy.deepcopy(base.connections),
                    )
                    latency_candidates.append((
                        f"tune-{cache.id}-hit-ratio",
                        [f"Tuned '{cache.id}' hit ratio from {curr_hit * 100:.0f}% to {tuned_hit * 100:.0f}% via index pre-warming"],
                        cand_graph,
                    ))

        # D. Database Read Replica addition
        for db in db_comps:
            db_read_comps = copy.deepcopy(base.components)
            for c in db_read_comps:
                if c.id == db.id:
                    c.replicas += 1
            cand_graph = ArchitectureGraph(
                components=db_read_comps,
                connections=copy.deepcopy(base.connections),
            )
            latency_candidates.append((
                f"add-{db.id}-read-replica",
                [f"Added read replica to '{db.id}' (replicas from {db.replicas} to {db.replicas + 1}) for read traffic scaling"],
                cand_graph,
            ))

        # ---------------------------------------------------------------------
        # 3. Throughput-Maximizing Mutations
        # ---------------------------------------------------------------------
        # A. Aggressive Bottleneck Scaling
        if base.components:
            bottleneck = min(base.components, key=lambda c: c.capacity_rps * c.replicas)
            bottle_comps = copy.deepcopy(base.components)
            for c in bottle_comps:
                if c.id == bottleneck.id:
                    if c.type in (ComponentType.API_SERVER, ComponentType.LOAD_BALANCER):
                        c.replicas += 2
                    else:
                        c.capacity_rps = round(c.capacity_rps * 2.0, 1)
                        c.cost_per_month_usd = round(c.cost_per_month_usd * 1.5, 2)
            cand_graph = ArchitectureGraph(
                components=bottle_comps,
                connections=copy.deepcopy(base.connections),
            )
            throughput_candidates.append((
                f"scale-{bottleneck.id}-max-capacity",
                [f"Aggressively expanded bottleneck '{bottleneck.id}' capacity to maximize peak throughput headroom"],
                cand_graph,
            ))

        # B. High-Throughput Clustered Scale (+2 API replicas, +1 DB replica)
        clustered_comps = copy.deepcopy(base.components)
        has_api_or_db = False
        for c in clustered_comps:
            if c.type == ComponentType.API_SERVER:
                c.replicas += 2
                has_api_or_db = True
            elif c.type == ComponentType.DATABASE:
                c.replicas += 1
                has_api_or_db = True
        if has_api_or_db:
            cand_graph = ArchitectureGraph(
                components=clustered_comps,
                connections=copy.deepcopy(base.connections),
            )
            throughput_candidates.append((
                "high-throughput-clustered-scale",
                ["Expanded cluster concurrency: +2 API replicas and +1 Database replica for peak throughput"],
                cand_graph,
            ))

        # C. API Concurrency Scaling (+2 replicas)
        for api in api_comps:
            c2_comps = copy.deepcopy(base.components)
            for c in c2_comps:
                if c.id == api.id:
                    c.replicas += 2
            cand_graph = ArchitectureGraph(
                components=c2_comps,
                connections=copy.deepcopy(base.connections),
            )
            throughput_candidates.append((
                f"scale-{api.id}-plus-2",
                [f"Scaled '{api.id}' replicas from {api.replicas} to {api.replicas + 2}"],
                cand_graph,
            ))

        # D. Scale Cache Throughput Capacity
        if cache_comps:
            for cache in cache_comps:
                cache_cap_comps = copy.deepcopy(base.components)
                new_cap = round(cache.capacity_rps * 1.5, 1)
                new_cost = round(cache.cost_per_month_usd * 1.25, 2)
                for c in cache_cap_comps:
                    if c.id == cache.id:
                        c.capacity_rps = new_cap
                        c.cost_per_month_usd = new_cost
                cand_graph = ArchitectureGraph(
                    components=cache_cap_comps,
                    connections=copy.deepcopy(base.connections),
                )
                throughput_candidates.append((
                    f"scale-{cache.id}-capacity",
                    [f"Scaled '{cache.id}' capacity from {cache.capacity_rps} to {new_cap} RPS"],
                    cand_graph,
                ))

        # ---------------------------------------------------------------------
        # 4. Balanced Composites
        # ---------------------------------------------------------------------
        # A. API Scale + Cache Hit Tuning
        if api_comps and cache_comps:
            comp_comps = copy.deepcopy(base.components)
            api_id = api_comps[0].id
            cache_id = cache_comps[0].id
            for c in comp_comps:
                if c.id == api_id:
                    c.replicas += 1
                elif c.id == cache_id and (c.cache_hit_ratio or 0.8) < 0.95:
                    c.cache_hit_ratio = min(0.95, round((c.cache_hit_ratio or 0.8) + 0.10, 2))
            cand_graph = ArchitectureGraph(
                components=comp_comps,
                connections=copy.deepcopy(base.connections),
            )
            balanced_candidates.append((
                "composite-api-scale-cache-tune",
                [
                    f"Scaled '{api_id}' replicas to {api_comps[0].replicas + 1}",
                    f"Tuned '{cache_id}' cache hit ratio to {cand_graph.get_component(cache_id).cache_hit_ratio * 100:.0f}%",
                ],
                cand_graph,
            ))

        # B. Scale +1 API Replica
        for api in api_comps:
            c1_comps = copy.deepcopy(base.components)
            for c in c1_comps:
                if c.id == api.id:
                    c.replicas += 1
            cand_graph = ArchitectureGraph(
                components=c1_comps,
                connections=copy.deepcopy(base.connections),
            )
            balanced_candidates.append((
                f"scale-{api.id}-plus-1",
                [f"Scaled '{api.id}' replicas from {api.replicas} to {api.replicas + 1}"],
                cand_graph,
            ))

        # C. API Scale + Database Upgrade
        if api_comps and db_comps:
            comp_db_comps = copy.deepcopy(base.components)
            api_id = api_comps[0].id
            db_id = db_comps[0].id
            for c in comp_db_comps:
                if c.id == api_id:
                    c.replicas += 1
                elif c.id == db_id:
                    c.capacity_rps = round(c.capacity_rps * 1.5, 1)
                    c.cost_per_month_usd = round(c.cost_per_month_usd * 1.4, 2)
            cand_graph = ArchitectureGraph(
                components=comp_db_comps,
                connections=copy.deepcopy(base.connections),
            )
            balanced_candidates.append((
                "composite-api-scale-db-upgrade",
                [
                    f"Scaled '{api_id}' replicas to {api_comps[0].replicas + 1}",
                    f"Upgraded '{db_id}' capacity to {round(db_comps[0].capacity_rps * 1.5, 1)} RPS",
                ],
                cand_graph,
            ))

        # ---------------------------------------------------------------------
        # 5. Objective-Aware Candidate Pool Prioritization
        # ---------------------------------------------------------------------
        if self.objective == OptimizationObjective.MINIMIZE_COST:
            candidate_pool = cost_candidates + latency_candidates + balanced_candidates + throughput_candidates
        elif self.objective == OptimizationObjective.MINIMIZE_LATENCY:
            candidate_pool = latency_candidates + balanced_candidates + throughput_candidates + cost_candidates
        elif self.objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
            candidate_pool = throughput_candidates + balanced_candidates + latency_candidates + cost_candidates
        else:  # BALANCED
            candidate_pool = []
            max_len = max(len(balanced_candidates), len(latency_candidates), len(cost_candidates), len(throughput_candidates), 1)
            for idx in range(max_len):
                if idx < len(balanced_candidates):
                    candidate_pool.append(balanced_candidates[idx])
                if idx < len(latency_candidates):
                    candidate_pool.append(latency_candidates[idx])
                if idx < len(cost_candidates):
                    candidate_pool.append(cost_candidates[idx])
                if idx < len(throughput_candidates):
                    candidate_pool.append(throughput_candidates[idx])

        # Deduplicate candidates by graph signature to guarantee distinct configurations
        seen_sigs = {base_sig}
        unique_candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []
        for cand_id, mods, graph in candidate_pool:
            sig = _graph_signature(graph)
            if sig not in seen_sigs:
                seen_sigs.add(sig)
                unique_candidates.append((cand_id, mods, graph))

        # If deduplication left fewer candidates than max_candidates, backfill any remaining valid candidates
        if len(unique_candidates) < self.max_candidates:
            all_fallback = (
                cost_candidates + latency_candidates + throughput_candidates + balanced_candidates
            )
            for cand_id, mods, graph in all_fallback:
                sig = _graph_signature(graph)
                if sig not in seen_sigs:
                    seen_sigs.add(sig)
                    unique_candidates.append((cand_id, mods, graph))

        return unique_candidates[: self.max_candidates]

    def _compute_objective_scores(
        self,
        evaluated_candidates: List[dict],
    ) -> None:
        """Compute objective scores and rank feasible candidates ahead of infeasible ones.

        Ranking principles:
        1. Feasible candidates (satisfying all hard constraints) ALWAYS rank above infeasible ones.
        2. Within feasible candidates:
           - MINIMIZE_LATENCY: Sort by p95 latency ascending, tie-breaker cost ascending, then throughput descending.
           - MINIMIZE_COST: Sort by monthly cost ascending, tie-breaker p95 latency ascending, then throughput descending.
           - MAXIMIZE_THROUGHPUT: Sort by throughput descending, tie-breaker bottleneck headroom descending, then p95 latency ascending.
           - BALANCED: Multi-criteria normalized score (0.35 latency + 0.30 cost + 0.20 throughput + 0.15 error).
        """
        if not evaluated_candidates:
            return

        latencies = [c["metrics"].p95_latency_ms for c in evaluated_candidates]
        costs = [c["metrics"].total_monthly_cost_usd for c in evaluated_candidates]
        throughputs = [c["metrics"].throughput_rps for c in evaluated_candidates]
        errors = [c["metrics"].error_rate for c in evaluated_candidates]

        min_lat, max_lat = min(latencies), max(latencies)
        min_cost, max_cost = min(costs), max(costs)
        min_tp, max_tp = min(throughputs), max(throughputs)
        min_err, max_err = min(errors), max(errors)

        lat_range = max(1e-6, max_lat - min_lat)
        cost_range = max(1e-6, max_cost - min_cost)
        tp_range = max(1e-6, max_tp - min_tp)
        err_range = max(1e-6, max_err - min_err)

        for c in evaluated_candidates:
            m: PerformanceMetrics = c["metrics"]
            is_feas: bool = c["is_feasible"]
            cand_graph: ArchitectureGraph = c["architecture"]

            # Effective bottleneck capacity headroom across components
            bottleneck_cap = min(comp.capacity_rps * comp.replicas for comp in cand_graph.components) if cand_graph.components else 0.0
            c["bottleneck_capacity"] = bottleneck_cap

            # Calculate normalized scores in [0, 1] (lower is better)
            norm_lat = (m.p95_latency_ms - min_lat) / lat_range
            norm_cost = (m.total_monthly_cost_usd - min_cost) / cost_range
            norm_tp = (max_tp - m.throughput_rps) / tp_range
            norm_err = (m.error_rate - min_err) / err_range

            if self.objective == OptimizationObjective.MINIMIZE_LATENCY:
                score = m.p95_latency_ms
            elif self.objective == OptimizationObjective.MINIMIZE_COST:
                score = m.total_monthly_cost_usd
            elif self.objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
                score = m.throughput_rps
            else:  # BALANCED
                score = (
                    0.35 * norm_lat
                    + 0.30 * norm_cost
                    + 0.20 * norm_tp
                    + 0.15 * norm_err
                )

            # Infeasible penalty to ensure feasible candidates always rank first
            if not is_feas:
                score += 100000.0

            c["score"] = round(float(score), 4)

        # Multi-attribute sorting ensuring feasible candidates rank first,
        # with objective-specific secondary and tertiary tie-breakers.
        if self.objective == OptimizationObjective.MINIMIZE_COST:
            evaluated_candidates.sort(
                key=lambda x: (
                    0 if x["is_feasible"] else 1,
                    x["metrics"].total_monthly_cost_usd,  # Primary: lowest cost
                    x["metrics"].p95_latency_ms,          # Secondary: lowest latency
                    -x["metrics"].throughput_rps,         # Tertiary: highest throughput
                    x["candidate_id"],                    # Deterministic final tie-breaker
                )
            )
        elif self.objective == OptimizationObjective.MINIMIZE_LATENCY:
            evaluated_candidates.sort(
                key=lambda x: (
                    0 if x["is_feasible"] else 1,
                    x["metrics"].p95_latency_ms,          # Primary: lowest latency
                    x["metrics"].total_monthly_cost_usd,  # Secondary: lowest cost
                    -x["metrics"].throughput_rps,         # Tertiary: highest throughput
                    x["candidate_id"],
                )
            )
        elif self.objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
            evaluated_candidates.sort(
                key=lambda x: (
                    0 if x["is_feasible"] else 1,
                    -x["metrics"].throughput_rps,         # Primary: highest throughput
                    -x["bottleneck_capacity"],            # Secondary: highest capacity headroom
                    x["metrics"].p95_latency_ms,          # Tertiary: lowest latency
                    x["metrics"].total_monthly_cost_usd,  # Quaternary: lowest cost
                    x["candidate_id"],
                )
            )
        else:  # BALANCED
            evaluated_candidates.sort(
                key=lambda x: (
                    0 if x["is_feasible"] else 1,
                    x["score"],                           # Primary: Pareto composite score
                    x["metrics"].p95_latency_ms,          # Secondary: lower latency
                    x["metrics"].total_monthly_cost_usd,  # Tertiary: lower cost
                    x["candidate_id"],
                )
            )

        for rank, c in enumerate(evaluated_candidates, start=1):
            c["rank"] = rank

        return evaluated_candidates

    def _generate_trade_off_analysis(
        self,
        baseline: PerformanceMetrics,
        recommended: Optional[CandidateArchitecture],
        feasible_count: int,
        total_count: int,
    ) -> str:
        """Generate human-readable trade-off and recommendation summary."""
        if not recommended:
            return (
                f"No candidate architecture satisfied all hard constraints out of {total_count} evaluated candidates. "
                "Consider increasing the monthly infrastructure budget or relaxing latency/throughput constraints."
            )

        m = recommended.metrics
        lat_change = ((m.p95_latency_ms - baseline.p95_latency_ms) / max(1e-3, baseline.p95_latency_ms)) * 100
        cost_change = m.total_monthly_cost_usd - baseline.total_monthly_cost_usd
        tp_change = ((m.throughput_rps - baseline.throughput_rps) / max(1e-3, baseline.throughput_rps)) * 100

        lines = [
            f"Evaluated {total_count} candidate architectures; {feasible_count} met all hard constraints.",
            f"Recommended Candidate: '{recommended.candidate_id}' under objective '{self.objective.value}'.",
            f"- Modifications: {'; '.join(recommended.modifications)}",
            f"- p95 Latency: {baseline.p95_latency_ms:.2f} ms -> {m.p95_latency_ms:.2f} ms ({lat_change:+.1f}%)",
            f"- Throughput: {baseline.throughput_rps:.1f} RPS -> {m.throughput_rps:.1f} RPS ({tp_change:+.1f}%)",
            f"- Monthly Cost: ${baseline.total_monthly_cost_usd:.2f} -> ${m.total_monthly_cost_usd:.2f} ({cost_change:+.2f} USD)",
            f"- Error Rate: {baseline.error_rate * 100:.2f}% -> {m.error_rate * 100:.2f}%",
        ]
        if self.objective == OptimizationObjective.MINIMIZE_COST:
            if cost_change < 0:
                lines.append(f"Trade-off: Prioritized infrastructure cost minimization, reducing monthly spend by ${abs(cost_change):.2f}/mo while meeting all performance SLAs.")
            else:
                lines.append(f"Trade-off: Cost minimization selected the lowest-cost feasible configuration (${m.total_monthly_cost_usd:.2f}/mo).")
        elif self.objective == OptimizationObjective.MINIMIZE_LATENCY:
            lines.append(f"Trade-off: Prioritized latency minimization, achieving p95 latency of {m.p95_latency_ms:.2f} ms ({lat_change:+.1f}% vs baseline).")
        elif self.objective == OptimizationObjective.MAXIMIZE_THROUGHPUT:
            lines.append(f"Trade-off: Prioritized peak throughput expansion and concurrency headroom ({m.throughput_rps:.1f} RPS completed).")
        else:
            if lat_change < 0 and cost_change > 0:
                lines.append(f"Trade-off: Balanced optimization invested ${cost_change:.2f}/mo to reduce p95 latency by {abs(lat_change):.1f}%.")
            elif cost_change < 0:
                lines.append(f"Trade-off: Balanced optimization reduced monthly cost by ${abs(cost_change):.2f} while satisfying performance constraints.")
            else:
                lines.append("Trade-off: Balanced multi-objective Pareto optimization achieved without violating performance or budget thresholds.")

        return "\n".join(lines)

    def optimize(self) -> OptimizationResult:
        """Run baseline and candidate simulations, enforce constraints, and rank candidates."""
        # 1. Run baseline simulation
        baseline_engine = SimulationEngine(
            graph=self.baseline_architecture,
            workload=self.workload,
            constraints=self.constraints,
        )
        baseline_res = baseline_engine.run()
        baseline_metrics = baseline_res.metrics

        # 2. Generate candidate topologies
        candidate_graphs = self._generate_candidate_graphs()

        # 3. Simulate each candidate under identical workload and seed
        evaluated_candidates: List[dict] = []
        for cand_id, mods, cand_graph in candidate_graphs:
            sim = SimulationEngine(
                graph=cand_graph,
                workload=self.workload,
                constraints=self.constraints,
            )
            sim_res = sim.run()

            # Check feasibility against hard constraints and error rate
            is_feasible = (
                len(sim_res.constraint_violations) == 0
                and sim_res.metrics.error_rate <= (self.constraints.max_error_rate if self.constraints and self.constraints.max_error_rate is not None else 0.05)
            )

            evaluated_candidates.append({
                "candidate_id": cand_id,
                "description": f"Candidate optimizing {', '.join(mods)}",
                "modifications": mods,
                "architecture": cand_graph,
                "metrics": sim_res.metrics,
                "constraint_violations": sim_res.constraint_violations,
                "is_feasible": is_feasible,
            })

        # 4. Rank candidates according to objective
        self._compute_objective_scores(evaluated_candidates)

        ranked_models = [
            CandidateArchitecture(
                candidate_id=c["candidate_id"],
                description=c["description"],
                modifications=c["modifications"],
                architecture=c["architecture"],
                metrics=c["metrics"],
                constraint_violations=c["constraint_violations"],
                is_feasible=c["is_feasible"],
                objective_score=c["score"],
                rank=c["rank"],
            )
            for c in evaluated_candidates
        ]

        feasible_candidates = [c for c in ranked_models if c.is_feasible]
        recommended: Optional[CandidateArchitecture] = feasible_candidates[0] if feasible_candidates else None
        status = "success" if recommended is not None else "no_feasible_candidate"

        trade_off_summary = self._generate_trade_off_analysis(
            baseline=baseline_metrics,
            recommended=recommended,
            feasible_count=len(feasible_candidates),
            total_count=len(ranked_models),
        )

        return OptimizationResult(
            status=status,
            objective=self.objective,
            baseline_metrics=baseline_metrics,
            total_candidates_evaluated=len(ranked_models),
            feasible_candidates_count=len(feasible_candidates),
            recommended_candidate=recommended,
            ranked_candidates=ranked_models,
            trade_off_analysis=trade_off_summary,
        )


def optimize_architecture(
    architecture: ArchitectureGraph,
    workload: WorkloadConfig,
    constraints: Optional[Constraints] = None,
    objective: OptimizationObjective = OptimizationObjective.BALANCED,
    max_candidates: int = 8,
) -> OptimizationResult:
    """Convenience functional interface to optimize an architecture."""
    optimizer = ArchitectureOptimizer(
        architecture=architecture,
        workload=workload,
        constraints=constraints,
        objective=objective,
        max_candidates=max_candidates,
    )
    return optimizer.optimize()
