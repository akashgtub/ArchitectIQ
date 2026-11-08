"""
ArchitectIQ DevSecOps - Synthetic Fixture Policy Enforcement Test Suite
Tests STRICT vs ADVISORY gatekeeper evaluations across all 9 required edge cases:
- No findings
- Low findings
- Medium findings
- High findings
- Critical findings
- Missing scanner
- Missing credentials
- Malformed scanner output
- Scanner execution error
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from security.framework.gatekeeper import PolicyGatekeeper
from security.framework.normalizer import SecurityGateReport

POLICY_YAML = Path(__file__).resolve().parent.parent / "policies" / "security-thresholds.yaml"


def create_fixture_report(
    path: Path,
    gate_id: str,
    status: str,
    verdict: str,
    critical: int = 0,
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    error_info: str = None,
) -> Path:
    rep = SecurityGateReport(
        gate_id=gate_id,
        gate_name=f"Test Gate ({gate_id})",
        tool_name="test-scanner",
        tool_version="1.0.0",
        execution_status=status,
        severity_verdict=verdict,
        finding_counts={"critical": critical, "high": high, "medium": medium, "low": low, "info": 0},
        error_information=error_info,
        report_location=str(path),
    )
    rep.write_json(path)
    return path


def test_scenario(name: str, setup_fn, expected_strict: str, expected_advisory: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        setup_fn(tmp_path)

        # STRICT evaluation
        gk_strict = PolicyGatekeeper(POLICY_YAML, mode="STRICT")
        res_strict = gk_strict.evaluate_reports(tmp_path)
        assert res_strict["overall_verdict"] == expected_strict, (
            f"[{name}] STRICT expected {expected_strict}, got {res_strict['overall_verdict']}: {res_strict['decision_reasons']}"
        )

        # ADVISORY evaluation
        gk_advisory = PolicyGatekeeper(POLICY_YAML, mode="ADVISORY")
        res_advisory = gk_advisory.evaluate_reports(tmp_path)
        assert res_advisory["overall_verdict"] == expected_advisory, (
            f"[{name}] ADVISORY expected {expected_advisory}, got {res_advisory['overall_verdict']}: {res_advisory['decision_reasons']}"
        )

        print(f"  PASS: Scenario '{name}' -> STRICT={res_strict['overall_verdict']}, ADVISORY={res_advisory['overall_verdict']}")


def run_all_fixture_tests():
    print("Running Synthetic Policy Enforcement Tests across 9 scenarios...")

    # 1. No findings
    def s1(p):
        create_fixture_report(p / "gate-01-trufflehog.json", "gate-01-trufflehog", "PASS", "PASS")
    test_scenario("1. No findings", s1, "APPROVED", "APPROVED")

    # 2. Low findings
    def s2(p):
        create_fixture_report(p / "gate-05-bandit.json", "gate-05-bandit", "PASS", "PASS", low=5)
    test_scenario("2. Low findings", s2, "APPROVED", "APPROVED")

    # 3. Medium findings
    def s3(p):
        create_fixture_report(p / "gate-05-bandit.json", "gate-05-bandit", "PASS", "PASS", medium=3)
    test_scenario("3. Medium findings", s3, "APPROVED", "APPROVED")

    # 4. High findings
    def s4(p):
        create_fixture_report(p / "gate-05-bandit.json", "gate-05-bandit", "FAIL", "FAIL", high=2)
    test_scenario("4. High findings", s4, "BLOCKED", "APPROVED")

    # 5. Critical findings
    def s5(p):
        create_fixture_report(p / "gate-01-trufflehog.json", "gate-01-trufflehog", "FAIL", "FAIL", critical=1)
    test_scenario("5. Critical findings", s5, "BLOCKED", "APPROVED")

    # 6. Missing scanner
    def s6(p):
        create_fixture_report(p / "gate-02-hadolint.json", "gate-02-hadolint", "BLOCKED", "BLOCKED", error_info="Hadolint binary not found on PATH")
    test_scenario("6. Missing scanner", s6, "BLOCKED", "APPROVED")

    # 7. Missing credentials
    def s7(p):
        create_fixture_report(p / "gate-08-snyk.json", "gate-08-snyk", "BLOCKED", "BLOCKED", error_info="Missing SNYK_TOKEN credentials")
    test_scenario("7. Missing credentials", s7, "BLOCKED", "APPROVED")

    # 8. Malformed scanner output
    def s8(p):
        (p / "gate-03-checkov.json").write_text("{ this is malformed json !!!", encoding="utf-8")
    test_scenario("8. Malformed scanner output", s8, "BLOCKED", "APPROVED")

    # 9. Scanner execution error
    def s9(p):
        create_fixture_report(p / "gate-10-owasp-zap.json", "gate-10-owasp-zap", "ERROR", "FAIL", error_info="Connection reset by peer during scan")
    test_scenario("9. Scanner execution error", s9, "BLOCKED", "APPROVED")

    print("\nAll 9 Policy Enforcement Scenarios VERIFIED successfully!")


if __name__ == "__main__":
    run_all_fixture_tests()
