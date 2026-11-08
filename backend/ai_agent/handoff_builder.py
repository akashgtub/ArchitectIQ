"""
ArchPilot AI - Member 2 Optimization Handoff Builder
Member 1: Architecture Understanding & Root-Cause Investigation

Assembles a validated, structured Member1Handoff object ready for direct
consumption by Member 2's optimization engine.
Enforces preservation of hard constraints, evidence traceability, and
truthful labelling of mock or incomplete simulations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.config import settings
from backend.shared.schemas import (
    Architecture,
    ArchitectureValidationResult,
    BaselineSimulationResponse,
    ConfirmedFinding,
    EvidenceReference,
    HypothesisStatus,
    InvestigationStatus,
    Member1Handoff,
    OptimizationHandoff,
    Provenance,
    RootCauseAnalysisResult,
    RootCauseHypothesis,
    SCHEMA_VERSION,
)

logger = logging.getLogger("archpilot.handoff_builder")


class HandoffBuilder:
    """
    Constructs and validates the definitive Member1Handoff contract.
    """

    def build_handoff(
        self,
        investigation_id: str,
        architecture: Architecture,
        validation_result: ArchitectureValidationResult,
        baseline: BaselineSimulationResponse,
        root_cause_result: RootCauseAnalysisResult,
        model_id: Optional[str] = None,
    ) -> Member1Handoff:
        """
        Builds and validates the complete Member1Handoff JSON payload.
        """
        # 1. Distinguish hard constraints from optimization preferences
        hard_constraints: Dict[str, Any] = {}
        constraints = architecture.constraints

        if constraints.max_p95_latency_ms is not None:
            hard_constraints["max_p95_latency_ms"] = constraints.max_p95_latency_ms
        if constraints.min_throughput_rps is not None:
            hard_constraints["min_throughput_rps"] = constraints.min_throughput_rps
        if constraints.max_cost_per_hour is not None:
            hard_constraints["max_cost_per_hour"] = constraints.max_cost_per_hour
        if constraints.min_availability is not None:
            hard_constraints["min_availability"] = constraints.min_availability

        # 2. Extract confirmed findings vs unconfirmed hypotheses
        confirmed_findings: List[ConfirmedFinding] = []
        ranked_hypotheses: List[RootCauseHypothesis] = []
        recommended_targets: List[str] = []

        # Sort hypotheses: CONFIRMED first, then TESTED_SUPPORTED, CANDIDATE, etc.
        priority_map = {
            HypothesisStatus.CONFIRMED: 0,
            HypothesisStatus.SUPPORTED: 1,
            HypothesisStatus.TESTED_SUPPORTED: 1,
            HypothesisStatus.CANDIDATE: 2,
            HypothesisStatus.INSUFFICIENT_EVIDENCE: 3,
            HypothesisStatus.INCONCLUSIVE: 4,
            HypothesisStatus.REJECTED: 5,
            HypothesisStatus.TESTED_WEAKENED: 5,
        }
        sorted_hypotheses = sorted(
            root_cause_result.hypotheses,
            key=lambda h: priority_map.get(h.status, 99)
        )

        for i, hyp in enumerate(sorted_hypotheses):
            ranked_hypotheses.append(hyp)
            for comp_id in hyp.affected_components:
                if comp_id not in recommended_targets:
                    recommended_targets.append(comp_id)

            if hyp.status == HypothesisStatus.CONFIRMED:
                finding = ConfirmedFinding(
                    finding_id=f"FINDING-{len(confirmed_findings) + 1:03d}",
                    title=hyp.title,
                    affected_components=hyp.affected_components,
                    evidence_references=hyp.supporting_evidence,
                    impact_summary=(
                        f"Confirmed bottleneck in {', '.join(hyp.affected_components)}. "
                        f"{hyp.description}"
                    ),
                )
                confirmed_findings.append(finding)

        # 3. Assemble assumptions to preserve
        assumptions_to_preserve: List[str] = list(validation_result.assumptions)
        assumptions_to_preserve.extend(baseline.assumptions)
        assumptions_to_preserve.append(
            f"Preserve baseline workload: {architecture.workload.requests_per_second} RPS "
            f"({architecture.workload.read_ratio*100:.0f}% read / {architecture.workload.write_ratio*100:.0f}% write)."
        )

        # 4. Warnings and alerts
        warnings: List[str] = list(baseline.warnings)
        if baseline.is_mock:
            warnings.append("NOTICE: Baseline and diagnostic metrics were generated using the deterministic mock simulator adapter.")
        if root_cause_result.status == InvestigationStatus.PARTIAL:
            warnings.append("WARNING: Investigation reached safety budget limits before all hypotheses could be fully tested.")
        if validation_result.unresolved_questions:
            warnings.append(
                f"WARNING: There are {len(validation_result.unresolved_questions)} unresolved clarification questions."
            )

        # 5. Assemble OptimizationHandoff
        opt_handoff = OptimizationHandoff(
            confirmed_findings=confirmed_findings,
            ranked_hypotheses=ranked_hypotheses,
            recommended_targets=recommended_targets,
            hard_constraints=hard_constraints,
            required_comparison_metrics=[
                "p95_latency_ms",
                "throughput_rps",
                "cost_per_hour",
                "availability",
            ],
            assumptions_to_preserve=assumptions_to_preserve,
            warnings=warnings,
        )

        # 6. Provenance metadata
        resolved_model_id = model_id or (settings.gemini_model_id if settings.gemini_api_key else "mock-extractor")
        prov = Provenance(
            model_id=resolved_model_id,
            simulator_version=baseline.simulator_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            schema_version=SCHEMA_VERSION,
        )

        # 7. Construct final Member1Handoff and validate against Pydantic schema
        handoff = Member1Handoff(
            schema_version=SCHEMA_VERSION,
            investigation_id=investigation_id,
            status=root_cause_result.status,
            architecture=architecture,
            architecture_validation=validation_result,
            baseline=baseline,
            root_cause_analysis=root_cause_result,
            optimization_handoff=opt_handoff,
            provenance=prov,
        )

        return handoff
