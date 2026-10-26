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
)


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
        """Generate a bounded set of valid alternative architecture graphs.

        Returns list of tuples: (candidate_id, modifications_list, modified_graph)
        """
        candidates: List[Tuple[str, List[str], ArchitectureGraph]] = []
        base = self.baseline_architecture

        # 1. API Server Replica Scaling (+1, +2)
        api_comps = [c for c in base.components if c.type == ComponentType.API_SERVER]
        for api in api_comps:
            # Candidate: Scale +1 replica
            c1_comps = copy.deepcopy(base.components)
            for c in c1_comps:
                if c.id == api.id:
                    c.replicas += 1
            cand1_graph = ArchitectureGraph(
                components=c1_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                f"scale-{api.id}-plus-1",
                [f"Scaled '{api.id}' replicas from {api.replicas} to {api.replicas + 1}"],
                cand1_graph,
            ))

            # Candidate: Scale +2 replicas
            c2_comps = copy.deepcopy(base.components)
            for c in c2_comps:
                if c.id == api.id:
                    c.replicas += 2
            cand2_graph = ArchitectureGraph(
                components=c2_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                f"scale-{api.id}-plus-2",
                [f"Scaled '{api.id}' replicas from {api.replicas} to {api.replicas + 2}"],
                cand2_graph,
            ))

        # 2. Database Vertical Tier Upgrade (+50% capacity, +40% cost)
        db_comps = [c for c in base.components if c.type == ComponentType.DATABASE]
        for db in db_comps:
            db_up_comps = copy.deepcopy(base.components)
            for c in db_up_comps:
                if c.id == db.id:
                    new_cap = round(c.capacity_rps * 1.5, 1)
                    new_cost = round(c.cost_per_month_usd * 1.4, 2)
                    c.capacity_rps = new_cap
                    c.cost_per_month_usd = new_cost
            cand_db_graph = ArchitectureGraph(
                components=db_up_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                f"upgrade-{db.id}-tier",
                [
                    f"Upgraded '{db.id}' vertical tier: capacity from {db.capacity_rps} to {round(db.capacity_rps * 1.5, 1)} RPS, "
                    f"cost from ${db.cost_per_month_usd:.2f} to ${round(db.cost_per_month_usd * 1.4, 2):.2f}/mo"
                ],
                cand_db_graph,
            ))

            # Database Read Replica addition (+1 replica for read-traffic scaling)
            db_read_comps = copy.deepcopy(base.components)
            for c in db_read_comps:
                if c.id == db.id:
                    c.replicas += 1
            cand_db_read_graph = ArchitectureGraph(
                components=db_read_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                f"add-{db.id}-read-replica",
                [f"Added read replica to '{db.id}' (replicas from {db.replicas} to {db.replicas + 1}) for read traffic scaling"],
                cand_db_read_graph,
            ))

        # 3. Cache Optimization / Tuning
        cache_comps = [c for c in base.components if c.type == ComponentType.CACHE]
        if cache_comps:
            for cache in cache_comps:
                # Tuning cache hit ratio (TTL optimization / pre-warming)
                curr_hit = cache.cache_hit_ratio or 0.8
                if curr_hit < 0.95:
                    tuned_hit = min(0.95, round(curr_hit + 0.10, 2))
                    cache_tune_comps = copy.deepcopy(base.components)
                    for c in cache_tune_comps:
                        if c.id == cache.id:
                            c.cache_hit_ratio = tuned_hit
                    cand_tune_graph = ArchitectureGraph(
                        components=cache_tune_comps,
                        connections=copy.deepcopy(base.connections),
                    )
                    candidates.append((
                        f"tune-{cache.id}-hit-ratio",
                        [f"Tuned '{cache.id}' hit ratio from {curr_hit * 100:.0f}% to {tuned_hit * 100:.0f}% via index pre-warming"],
                        cand_tune_graph,
                    ))

                # Scaling cache capacity
                cache_cap_comps = copy.deepcopy(base.components)
                for c in cache_cap_comps:
                    if c.id == cache.id:
                        c.capacity_rps = round(c.capacity_rps * 1.5, 1)
                        c.cost_per_month_usd = round(c.cost_per_month_usd * 1.25, 2)
                cand_cache_cap_graph = ArchitectureGraph(
                    components=cache_cap_comps,
                    connections=copy.deepcopy(base.connections),
                )
                candidates.append((
                    f"scale-{cache.id}-capacity",
                    [f"Scaled '{cache.id}' capacity from {cache.capacity_rps} to {round(cache.capacity_rps * 1.5, 1)} RPS"],
                    cand_cache_cap_graph,
                ))

        # 4. Composite: API Replica Scale + Cache Hit Tuning
        if api_comps and cache_comps:
            comp_comps = copy.deepcopy(base.components)
            api_id = api_comps[0].id
            cache_id = cache_comps[0].id
            for c in comp_comps:
                if c.id == api_id:
                    c.replicas += 1
                elif c.id == cache_id and (c.cache_hit_ratio or 0.8) < 0.95:
                    c.cache_hit_ratio = min(0.95, round((c.cache_hit_ratio or 0.8) + 0.10, 2))
            cand_comp_graph = ArchitectureGraph(
                components=comp_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                "composite-api-scale-cache-tune",
                [
                    f"Scaled '{api_id}' replicas to {api_comps[0].replicas + 1}",
                    f"Tuned '{cache_id}' cache hit ratio to {cand_comp_graph.get_component(cache_id).cache_hit_ratio * 100:.0f}%",
                ],
                cand_comp_graph,
            ))

        # 5. Composite: API Replica Scale + Database Vertical Upgrade
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
            cand_comp_db_graph = ArchitectureGraph(
                components=comp_db_comps,
                connections=copy.deepcopy(base.connections),
            )
            candidates.append((
                "composite-api-scale-db-upgrade",
                [
                    f"Scaled '{api_id}' replicas to {api_comps[0].replicas + 1}",
                    f"Upgraded '{db_id}' capacity to {round(db_comps[0].capacity_rps * 1.5, 1)} RPS",
                ],
                cand_comp_db_graph,
            ))

        # Cap generated candidates by max_candidates limit
        return candidates[: self.max_candidates]

    def _compute_objective_scores(
        self,
        evaluated_candidates: List[dict],
    ) -> None:
        """Compute objective scores and rank feasible candidates ahead of infeasible ones.

        Ranking principles:
        1. Feasible candidates (satisfying all hard constraints) ALWAYS rank above infeasible ones.
        2. Within feasible candidates:
           - MINIMIZE_LATENCY: Sort by p95 latency ascending, tie-breaker cost ascending.
           - MINIMIZE_COST: Sort by monthly cost ascending, tie-breaker p95 latency ascending.
           - MAXIMIZE_THROUGHPUT: Sort by throughput descending, tie-breaker p95 latency ascending.
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
                score = -m.throughput_rps
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

        # Deterministic sorting key: (is_feasible DESC, score ASC, candidate_id ASC)
        evaluated_candidates.sort(
            key=lambda x: (
                0 if x["is_feasible"] else 1,
                x["score"],
                x["candidate_id"],
            )
        )

        for rank, c in enumerate(evaluated_candidates, start=1):
            c["rank"] = rank

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
        if lat_change < 0 and cost_change > 0:
            lines.append(f"Trade-off: Invested ${cost_change:.2f}/mo to reduce p95 latency by {abs(lat_change):.1f}%.")
        elif cost_change < 0:
            lines.append(f"Trade-off: Reduced monthly cost by ${abs(cost_change):.2f} while satisfying all performance constraints.")
        else:
            lines.append("Trade-off: Balanced optimization achieved without violating performance or budget thresholds.")

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
