"""
ArchitectIQ DevSecOps - Vault & Secrets Management Validation Contract (Gate 12)
Validates that secrets are managed through sanctioned stores (Kubernetes Secrets / HashiCorp Vault / Env Injection)
and verifies non-exposure across git and templates.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def validate_secrets_contract(repo_root: Path) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    checked_rules = 0

    # 1. Verify .gitignore ignores .env and private keys
    gitignore_path = repo_root / ".gitignore"
    checked_rules += 1
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if ".env" not in content:
            findings.append({
                "id": "SEC-VAULT-001",
                "severity": "CRITICAL",
                "message": ".gitignore must explicitly ignore .env files to prevent credential commits.",
                "file": ".gitignore",
            })
    else:
        findings.append({
            "id": "SEC-VAULT-002",
            "severity": "HIGH",
            "message": ".gitignore not found in repository root.",
            "file": ".gitignore",
        })

    # 2. Check .env.example contains only placeholders, no real secrets
    env_example = repo_root / ".env.example"
    checked_rules += 1
    if env_example.exists():
        lines = env_example.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if line.startswith("HF_TOKEN=") and not line.startswith("HF_TOKEN=hf_your_"):
                findings.append({
                    "id": "SEC-VAULT-003",
                    "severity": "CRITICAL",
                    "message": f".env.example line {i} contains non-placeholder HF_TOKEN value.",
                    "file": ".env.example",
                })
            if line.startswith("GEMINI_API_KEY=") and not line.startswith("GEMINI_API_KEY=your_"):
                findings.append({
                    "id": "SEC-VAULT-004",
                    "severity": "CRITICAL",
                    "message": f".env.example line {i} contains non-placeholder GEMINI_API_KEY value.",
                    "file": ".env.example",
                })

    # 3. Check Kubernetes secrets example template
    k8s_secret = repo_root / "infrastructure" / "kubernetes" / "secrets.example.yaml"
    checked_rules += 1
    if k8s_secret.exists():
        content = k8s_secret.read_text(encoding="utf-8")
        if "AIza" in content or "hf_" in content:
            findings.append({
                "id": "SEC-VAULT-005",
                "severity": "CRITICAL",
                "message": "infrastructure/kubernetes/secrets.example.yaml contains real secret pattern.",
                "file": "infrastructure/kubernetes/secrets.example.yaml",
            })

    # 4. Check backend config loads secrets via os.getenv (no hardcoded keys)
    backend_config = repo_root / "backend" / "config.py"
    checked_rules += 1
    if backend_config.exists():
        content = backend_config.read_text(encoding="utf-8")
        if "os.getenv(\"GEMINI_API_KEY\"" not in content and "os.getenv('GEMINI_API_KEY'" not in content:
            findings.append({
                "id": "SEC-VAULT-006",
                "severity": "HIGH",
                "message": "backend/config.py does not use os.getenv for GEMINI_API_KEY injection.",
                "file": "backend/config.py",
            })

    # Determine status
    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")

    return {
        "status": "PASS" if (critical_count == 0 and high_count == 0) else "FAIL",
        "checked_rules": checked_rules,
        "critical_count": critical_count,
        "high_count": high_count,
        "findings": findings,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    res = validate_secrets_contract(root)
    print(f"Vault Check Status: {res['status']} ({res['checked_rules']} rules evaluated, {len(res['findings'])} findings)")
    sys.exit(0 if res["status"] == "PASS" else 1)

