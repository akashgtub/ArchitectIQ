"""
ArchitectIQ DevSecOps - Policy Gatekeeper
Aggregates reports across all 12 security gates and enforces quality thresholds
under STRICT or ADVISORY policy modes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml


class PolicyGatekeeper:
    """Evaluates security reports against policy thresholds."""

    def __init__(self, policy_file: Path, mode: str = "STRICT"):
        self.policy_file = policy_file
        self.mode = mode.upper()
        self.policy = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        if not self.policy_file.exists():
            return {
                "enforcement_modes": {
                    "STRICT": {"max_critical": 0, "max_high": 0, "block_on_scanner_error": True},
                    "ADVISORY": {"max_critical": 999, "max_high": 999, "block_on_scanner_error": False},
                }
            }
        with open(self.policy_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def evaluate_reports(self, reports_dir: Path) -> Dict[str, Any]:
        mode_cfg = self.policy.get("enforcement_modes", {}).get(self.mode, {})
        max_crit = mode_cfg.get("max_critical", 0)
        max_high = mode_cfg.get("max_high", 0)
        block_on_err = mode_cfg.get("block_on_scanner_error", True)
        block_on_cred = mode_cfg.get("block_on_missing_credentials", True)
        block_on_missing_scanner = mode_cfg.get("block_on_missing_scanner", True)

        gate_results: Dict[str, Any] = {}
        total_findings = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        blocked_gates: List[str] = []
        failed_gates: List[str] = []
        scanner_errors: List[str] = []

        # Find all gate reports
        report_files = sorted(reports_dir.glob("gate-*.json"))
        # Exclude summary itself if present
        report_files = [f for f in report_files if not f.name.endswith("compliance-summary.json")]

        for rf in report_files:
            gate_key = rf.stem
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                # Malformed scanner output
                scanner_errors.append(f"{gate_key}: Malformed report JSON ({str(e)})")
                gate_results[gate_key] = {
                    "status": "ERROR",
                    "reason": f"Malformed JSON: {str(e)}",
                    "counts": {},
                }
                if block_on_err:
                    failed_gates.append(gate_key)
                continue

            status = data.get("execution_status", "UNKNOWN")
            verdict = data.get("severity_verdict", "UNKNOWN")
            counts = data.get("finding_counts", {})
            err_info = data.get("error_information")

            for k in total_findings:
                total_findings[k] += counts.get(k, 0)

            gate_results[gate_key] = {
                "name": data.get("gate_name", gate_key),
                "tool": data.get("tool_name", "unknown"),
                "status": status,
                "verdict": verdict,
                "counts": counts,
                "error_info": err_info,
            }

            if status == "FAIL" or verdict == "FAIL":
                failed_gates.append(gate_key)
            elif status == "BLOCKED" or verdict == "BLOCKED":
                blocked_gates.append(gate_key)
                err_lower = (err_info or "").lower()
                if block_on_cred and ("token" in err_lower or "credential" in err_lower):
                    failed_gates.append(gate_key)
                elif block_on_missing_scanner:
                    failed_gates.append(gate_key)
            elif status == "ERROR":
                scanner_errors.append(f"{gate_key}: {err_info}")
                if block_on_err:
                    failed_gates.append(gate_key)

        # Evaluate overall policy decision
        overall_pass = True
        decision_reasons: List[str] = []

        if self.mode == "STRICT":
            if total_findings["critical"] > max_crit:
                overall_pass = False
                decision_reasons.append(f"Critical findings ({total_findings['critical']}) exceed threshold ({max_crit})")
            if total_findings["high"] > max_high:
                overall_pass = False
                decision_reasons.append(f"High findings ({total_findings['high']}) exceed threshold ({max_high})")
            if scanner_errors and block_on_err:
                overall_pass = False
                decision_reasons.append(f"Scanner execution errors detected in {len(scanner_errors)} gates")
            if failed_gates:
                overall_pass = False
                decision_reasons.append(f"Gates failed quality verdict: {', '.join(failed_gates)}")
        else:
            # ADVISORY mode never blocks, but records real warnings
            decision_reasons.append("ADVISORY mode: Non-blocking audit evaluation")

        summary = {
            "policy_mode": self.mode,
            "overall_verdict": "APPROVED" if overall_pass else "BLOCKED",
            "decision_reasons": decision_reasons,
            "total_evaluated_reports": len(report_files),
            "aggregate_finding_counts": total_findings,
            "failed_gates": failed_gates,
            "blocked_gates": blocked_gates,
            "scanner_errors": scanner_errors,
            "gate_details": gate_results,
        }

        # Write summary report
        summary_path = reports_dir / "gate-12-compliance-summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return summary


def main():
    parser = argparse.ArgumentParser(description="ArchitectIQ Policy Gatekeeper")
    parser.add_argument("--reports-dir", type=str, required=True, help="Path to reports directory")
    parser.add_argument("--policy", type=str, default="security/policies/security-thresholds.yaml", help="Path to policy YAML")
    parser.add_argument("--mode", type=str, default="STRICT", choices=["STRICT", "ADVISORY"], help="Enforcement mode")
    args = parser.parse_args()

    gk = PolicyGatekeeper(Path(args.policy), mode=args.mode)
    res = gk.evaluate_reports(Path(args.reports_dir))

    print(f"============================================================")
    print(f"         ARCHITECTIQ DEVSECOPS POLICY GATEKEEPER            ")
    print(f"============================================================")
    print(f"Mode            : {res['policy_mode']}")
    print(f"Overall Verdict : {res['overall_verdict']}")
    print(f"Total Findings  : Critical={res['aggregate_finding_counts']['critical']}, High={res['aggregate_finding_counts']['high']}, Med={res['aggregate_finding_counts']['medium']}, Low={res['aggregate_finding_counts']['low']}")
    if res['decision_reasons']:
        print("Reasons         :")
        for r in res['decision_reasons']:
            print(f"  - {r}")
    print(f"============================================================")

    if args.mode == "STRICT" and res["overall_verdict"] == "BLOCKED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
