"""
ArchPilot AI - Root-Cause Investigation Engine
Member 1: Architecture Understanding & Root-Cause Investigation

Investigates bottlenecks using evidence-based reasoning from baseline simulation metrics
and targeted diagnostic experiments.
Enforces hypothesis generation, experiment allowlists, experiment ledgers,
safety budget limits, and strict traceability without fabricated metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from backend.config import settings
from backend.integrations.simulator_client import SimulatorClient, SimulatorClientError
from backend.shared.schemas import (
    Architecture,
    BaselineSimulationResponse,
    ComponentType,
    ConfidenceLabel,
    DiagnosticExperimentRequest,
    DiagnosticExperimentResponse,
    EvidenceReference,
    HypothesisStatus,
    InvestigationStatus,
    MetricDiff,
    RootCauseAnalysisResult,
    RootCauseHypothesis,
    SupportedDiagnosticExperiment,
)

logger = logging.getLogger("archpilot.root_cause")


class RootCauseInvestigator:
    """
    Orchestrates evidence-based root-cause hypothesis generation,
    diagnostic experiment dispatch, and results interpretation.
    """

    def __init__(
        self,
        simulator_client: Optional[SimulatorClient] = None,
        max_experiments: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.simulator_client = simulator_client or SimulatorClient()
        self.max_experiments = (
            max_experiments if max_experiments is not None else settings.max_diagnostic_experiments
        )
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.investigation_timeout_seconds
        )

    async def investigate(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
        investigation_id: str = "inv-001",
    ) -> RootCauseAnalysisResult:
        """
        Executes full investigation:
        1. Formulate initial hypotheses from baseline metrics.
        2. Select diagnostic experiments within budget.
        3. Dispatch experiments via simulator adapter and record in ledger.
        4. Re-evaluate hypotheses based on observed diffs.
        5. Return comprehensive evidence-based RootCauseAnalysisResult.
        """
        start_time = time.time()
        experiment_ledger: List[DiagnosticExperimentResponse] = []
        executed_experiment_types: Set[SupportedDiagnosticExperiment] = set()

        # Step 1: Formulate hypotheses from baseline measurements
        hypotheses = self.generate_hypotheses(architecture, baseline)

        # Step 2: Select and run diagnostic experiments up to budget limit
        for hyp in hypotheses:
            # Check budget limits: max experiments & time
            if len(experiment_ledger) >= self.max_experiments:
                logger.info(
                    "Reached maximum diagnostic experiment limit (%d). Stopping experiment loop.",
                    self.max_experiments,
                )
                break

            elapsed = time.time() - start_time
            if elapsed >= self.timeout_seconds:
                logger.warning(
                    "Investigation wall-clock timeout reached (%ds). Stopping experiment loop.",
                    self.timeout_seconds,
                )
                break

            # Pick recommended experiment from allowlist
            rec_exp = hyp.recommended_experiment
            if not rec_exp or rec_exp in executed_experiment_types:
                continue

            # Build experiment request
            exp_id = f"exp-{investigation_id}-{len(experiment_ledger) + 1:02d}"
            exp_request = self._build_experiment_request(
                experiment_id=exp_id,
                baseline=baseline,
                architecture=architecture,
                experiment_type=rec_exp,
                target_hypothesis=hyp,
            )

            # Execute via simulator client
            try:
                diag_resp = await self.simulator_client.run_diagnostic(
                    request=exp_request,
                    baseline=baseline,
                )
                experiment_ledger.append(diag_resp)
                executed_experiment_types.add(rec_exp)

                # Step 3: Interpret diagnostic results and update hypothesis
                self._update_hypothesis_with_experiment(hyp, diag_resp, baseline)

            except SimulatorClientError as e:
                logger.warning("Diagnostic experiment %s failed: %s", exp_id, e)
                # Keep hypothesis with note of experiment failure
                hyp.missing_evidence.append(f"Diagnostic experiment '{rec_exp.value}' failed: {e.message}")

        # Step 4: Final status determination and evidence summary
        evidence_summary: List[str] = []
        for hyp in hypotheses:
            if hyp.status == HypothesisStatus.CONFIRMED:
                evidence_summary.append(
                    f"CONFIRMED: {hyp.title} (affected: {', '.join(hyp.affected_components)}). "
                    f"Evidence points: {len(hyp.supporting_evidence)}."
                )
            elif hyp.status in (HypothesisStatus.SUPPORTED, HypothesisStatus.TESTED_SUPPORTED):
                evidence_summary.append(
                    f"SUPPORTED: {hyp.title} (affected: {', '.join(hyp.affected_components)}). "
                    f"Requires additional proof: {'; '.join(hyp.missing_evidence) or 'None'}."
                )
            elif hyp.status in (HypothesisStatus.REJECTED, HypothesisStatus.TESTED_WEAKENED):
                evidence_summary.append(
                    f"REJECTED/WEAKENED: {hyp.title} - Contradicted by experimental results."
                )
            elif hyp.status == HypothesisStatus.INSUFFICIENT_EVIDENCE:
                evidence_summary.append(
                    f"INSUFFICIENT EVIDENCE: {hyp.title} - Missing data: {'; '.join(hyp.missing_evidence)}."
                )

        overall_status = InvestigationStatus.COMPLETED
        if len(experiment_ledger) >= self.max_experiments and any(h.status == HypothesisStatus.CANDIDATE for h in hypotheses):
            overall_status = InvestigationStatus.PARTIAL

        return RootCauseAnalysisResult(
            status=overall_status,
            hypotheses=hypotheses,
            experiments=experiment_ledger,
            evidence_summary=evidence_summary,
        )

    def generate_hypotheses(
        self,
        architecture: Architecture,
        baseline: BaselineSimulationResponse,
    ) -> List[RootCauseHypothesis]:
        """
        Examines baseline metrics and architecture topology to formulate testable hypotheses.
        Uses controlled confidence labels ('low', 'medium', 'high').
        """
        hypotheses: List[RootCauseHypothesis] = []
        baseline_metrics = baseline.metrics
        p95 = baseline_metrics.get("p95_latency_ms")
        max_p95_constraint = architecture.constraints.max_p95_latency_ms

        db_comp = next((c for c in architecture.components if c.type == ComponentType.DATABASE), None)
        cache_comp = next((c for c in architecture.components if c.type == ComponentType.CACHE), None)
        api_comps = [c for c in architecture.components if c.type in (ComponentType.API_SERVER, ComponentType.MICROSERVICE)]

        # Find component metrics
        db_metric = next((m for m in baseline.component_metrics if db_comp and m.component_id == db_comp.id), None)
        api_metric = next((m for m in baseline.component_metrics if api_comps and m.component_id == api_comps[0].id), None)

        # 1. Hypothesis: Database Saturation / Queuing Bottleneck
        if db_metric and (db_metric.cpu_utilization_pct or 0.0) >= 70.0:
            supp_evidence: List[EvidenceReference] = [
                EvidenceReference(
                    run_id=baseline.run_id,
                    metric_name="cpu_utilization_pct",
                    observed_value=db_metric.cpu_utilization_pct,
                    baseline_value=db_metric.cpu_utilization_pct,
                    diff=0.0,
                    unit="%",
                    description=f"Database '{db_comp.id}' CPU utilization is high ({db_metric.cpu_utilization_pct:.1f}%) under baseline load.",
                )
            ]
            if p95 and max_p95_constraint and p95 > max_p95_constraint:
                supp_evidence.append(
                    EvidenceReference(
                        run_id=baseline.run_id,
                        metric_name="p95_latency_ms",
                        observed_value=p95,
                        baseline_value=p95,
                        diff=0.0,
                        unit="ms",
                        description=f"System baseline p95 latency ({p95}ms) exceeds target constraint ({max_p95_constraint}ms) by {p95 - max_p95_constraint:.1f}ms.",
                    )
                )

            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="HYP-001",
                    title="Database Processing and Queuing Bottleneck",
                    description=(
                        f"Database '{db_comp.id}' is operating at near capacity under the baseline {architecture.workload.requests_per_second} RPS workload. "
                        "High contention leads to request queue buildup and elevated p95 latency."
                    ),
                    affected_components=[db_comp.id] if db_comp else [],
                    supporting_evidence=supp_evidence,
                    contradicting_evidence=[],
                    missing_evidence=["Verification under increased load or DB read replica offloading"],
                    confidence_label=ConfidenceLabel.HIGH if (db_metric.cpu_utilization_pct or 0) > 80.0 else ConfidenceLabel.MEDIUM,
                    recommended_experiment=SupportedDiagnosticExperiment.INCREASE_WORKLOAD,
                    status=HypothesisStatus.CANDIDATE,
                )
            )

        # 2. Hypothesis: Cache Inefficiency / Cache Bypass
        if cache_comp and db_comp:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="HYP-002",
                    title="Cache Hit Ratio Degradation and DB Read Contention",
                    description=(
                        f"If read traffic bypasses cache '{cache_comp.id}', excessive read operations fall back to '{db_comp.id}', "
                        "exhausting database connection pools."
                    ),
                    affected_components=[cache_comp.id, db_comp.id],
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    missing_evidence=["Measurement of latency impact when cache is bypassed or disabled"],
                    confidence_label=ConfidenceLabel.LOW,
                    recommended_experiment=SupportedDiagnosticExperiment.TOGGLE_CACHE,
                    status=HypothesisStatus.CANDIDATE,
                )
            )

        # 3. Hypothesis: Write-Heavy Workload Contention
        if architecture.workload.write_ratio >= 0.2 and db_comp:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="HYP-003",
                    title="Write-Path Transaction Contention",
                    description=(
                        f"A write ratio of {architecture.workload.write_ratio*100:.0f}% may be causing lock contention "
                        f"and disk I/O wait on primary database '{db_comp.id}'."
                    ),
                    affected_components=[db_comp.id],
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    missing_evidence=["Comparison against varied read/write ratio mixes"],
                    confidence_label=ConfidenceLabel.MEDIUM if architecture.workload.write_ratio > 0.3 else ConfidenceLabel.LOW,
                    recommended_experiment=SupportedDiagnosticExperiment.VARY_READ_WRITE_MIX,
                    status=HypothesisStatus.CANDIDATE,
                )
            )

        # 4. Hypothesis: API Compute Tier Scaling Limit
        if api_metric and (api_metric.cpu_utilization_pct or 0.0) >= 60.0:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="HYP-004",
                    title="API Server Compute Tier Capacity Limit",
                    description=(
                        f"API tier component '{api_comps[0].id}' CPU utilization is elevated ({api_metric.cpu_utilization_pct:.1f}%), "
                        "suggesting insufficient horizontal worker replicas."
                    ),
                    affected_components=[api_comps[0].id],
                    supporting_evidence=[
                        EvidenceReference(
                            run_id=baseline.run_id,
                            metric_name="cpu_utilization_pct",
                            observed_value=api_metric.cpu_utilization_pct,
                            baseline_value=api_metric.cpu_utilization_pct,
                            diff=0.0,
                            unit="%",
                            description=f"API server CPU utilization at {api_metric.cpu_utilization_pct:.1f}%.",
                        )
                    ],
                    contradicting_evidence=[],
                    missing_evidence=["Latency reduction measurement upon scaling API server replicas"],
                    confidence_label=ConfidenceLabel.MEDIUM,
                    recommended_experiment=SupportedDiagnosticExperiment.SCALE_COMPONENT,
                    status=HypothesisStatus.CANDIDATE,
                )
            )

        # Fallback hypothesis if no obvious metrics triggered
        if not hypotheses:
            target_ids = [c.id for c in architecture.components[:2]]
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="HYP-000",
                    title="Baseline System Latency Under High Workload",
                    description="Evaluating system latency response under scaled load to detect latent bottlenecks.",
                    affected_components=target_ids,
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    missing_evidence=["Diagnostic stress test results"],
                    confidence_label=ConfidenceLabel.LOW,
                    recommended_experiment=SupportedDiagnosticExperiment.INCREASE_WORKLOAD,
                    status=HypothesisStatus.INSUFFICIENT_EVIDENCE,
                )
            )

        return hypotheses

    def _build_experiment_request(
        self,
        experiment_id: str,
        baseline: BaselineSimulationResponse,
        architecture: Architecture,
        experiment_type: SupportedDiagnosticExperiment,
        target_hypothesis: RootCauseHypothesis,
    ) -> DiagnosticExperimentRequest:
        """
        Builds a strictly validated DiagnosticExperimentRequest with explicit rationale.
        """
        params_to_change: Dict[str, Any] = {}
        fixed_params: Dict[str, Any] = {
            "workload_rps": architecture.workload.requests_per_second,
            "read_ratio": architecture.workload.read_ratio,
            "write_ratio": architecture.workload.write_ratio,
        }

        if experiment_type == SupportedDiagnosticExperiment.INCREASE_WORKLOAD:
            params_to_change["multiplier"] = 1.5
            reason = f"Increase load to 1.5x ({architecture.workload.requests_per_second * 1.5:.0f} RPS) to test queue saturation on {target_hypothesis.affected_components}."
            expected = "Non-linear increase in p95 latency confirms queuing/capacity bottleneck."

        elif experiment_type == SupportedDiagnosticExperiment.VARY_READ_WRITE_MIX:
            params_to_change["write_ratio"] = 0.5
            params_to_change["read_ratio"] = 0.5
            reason = "Vary read/write mix to 50/50 to observe sensitivity to write transactions."
            expected = "Disproportionate latency increase indicates database write lock contention."

        elif experiment_type == SupportedDiagnosticExperiment.SIMULATE_DB_LATENCY:
            params_to_change["db_latency_overhead_ms"] = 50.0
            reason = "Inject 50ms synthetic latency into database connection to isolate database contribution."
            expected = "Direct propagation to end-to-end latency confirms database as critical path dependency."

        elif experiment_type == SupportedDiagnosticExperiment.SCALE_COMPONENT:
            params_to_change["replicas"] = 2
            reason = f"Scale component {target_hypothesis.affected_components} by adding a replica."
            expected = "Significant drop in p95 latency confirms compute/connection pool starvation."

        elif experiment_type == SupportedDiagnosticExperiment.TOGGLE_CACHE:
            params_to_change["enabled"] = False
            reason = "Disable session cache to measure database degradation when handling all requests."
            expected = "Sharp increase in DB CPU and latency confirms cache offloading effectiveness."

        else:
            params_to_change["test_run"] = True
            reason = "Standard baseline verification"
            expected = "Metrics remain consistent"

        return DiagnosticExperimentRequest(
            experiment_id=experiment_id,
            baseline_run_id=baseline.run_id,
            experiment_type=experiment_type,
            target_components=target_hypothesis.affected_components,
            parameters_to_change=params_to_change,
            fixed_parameters=fixed_params,
            reason=reason,
            hypotheses_tested=[target_hypothesis.hypothesis_id],
            expected_evidence=expected,
        )

    def _update_hypothesis_with_experiment(
        self,
        hypothesis: RootCauseHypothesis,
        experiment: DiagnosticExperimentResponse,
        baseline: BaselineSimulationResponse,
    ):
        """
        Updates hypothesis status and records evidence based on actual MetricDiff observations.
        Does not claim confirmed cause without distinguishing evidence.
        """
        p95_diff = next((d for d in experiment.diff_from_baseline if d.metric_name == "p95_latency_ms"), None)

        if not p95_diff or p95_diff.diff_value is None:
            hypothesis.status = HypothesisStatus.INSUFFICIENT_EVIDENCE
            hypothesis.confidence_label = ConfidenceLabel.LOW
            hypothesis.missing_evidence.append(
                f"Experiment {experiment.experiment_id} did not yield a valid p95_latency_ms diff."
            )
            return

        # Create evidence reference from metric diff
        ev_ref = EvidenceReference(
            run_id=experiment.baseline_run_id,
            experiment_id=experiment.experiment_id,
            metric_name="p95_latency_ms",
            observed_value=p95_diff.diagnostic_value,
            baseline_value=p95_diff.baseline_value,
            diff=p95_diff.diff_value,
            unit=p95_diff.unit,
            description=f"Diagnostic experiment '{experiment.experiment_id}' observed delta of {p95_diff.diff_value:+.1f} {p95_diff.unit} ({p95_diff.diff_pct:+.1f}%). {p95_diff.interpretation}",
        )

        # Distinguish between supporting and contradicting results
        if p95_diff.diff_value > 0 and (p95_diff.diff_pct or 0.0) >= 20.0:
            # Significant degradation observed as predicted
            hypothesis.supporting_evidence.append(ev_ref)
            hypothesis.status = HypothesisStatus.CONFIRMED
            hypothesis.confidence_label = ConfidenceLabel.HIGH
            hypothesis.missing_evidence.clear()
        elif p95_diff.diff_value < -15.0:
            # Relieved bottleneck (e.g. scale_component reduced latency significantly)
            hypothesis.supporting_evidence.append(ev_ref)
            hypothesis.status = HypothesisStatus.CONFIRMED
            hypothesis.confidence_label = ConfidenceLabel.HIGH
            hypothesis.missing_evidence.clear()
        elif abs(p95_diff.diff_value) < 5.0:
            # No notable impact: hypothesis weakened or contradicted
            hypothesis.contradicting_evidence.append(ev_ref)
            hypothesis.status = HypothesisStatus.TESTED_WEAKENED
            hypothesis.confidence_label = ConfidenceLabel.LOW
        else:
            hypothesis.supporting_evidence.append(ev_ref)
            hypothesis.status = HypothesisStatus.TESTED_SUPPORTED
            hypothesis.confidence_label = ConfidenceLabel.MEDIUM
