# ArchitectIQ DevSecOps Security Framework (5 Essential Tools)

This directory contains the independent DevSecOps security automation framework for ArchitectIQ, incorporating five industry-standard security tools across static, dynamic, infrastructure, and secrets security analysis.

---

## 🏛️ Architecture & Component Isolation

In alignment with the enterprise platform design:
- **Application Isolation**: The application runtime (`docker-compose.yml`) contains **zero** security scanners or external dependencies.
- **Independent Virtual Environment**: Python scanners (Bandit, Checkov) run inside `security/.venv`, strictly isolated from the backend's FastAPI runtime dependencies.
- **Resource Safeguards**: Automated available RAM detection safeguards system stability before scanner execution.
- **Standardized Reports**: All tools output standardized machine-readable JSON to `reports/security/gate-0X-<tool>.json` and human-readable summaries to `reports/security/security-summary.md`.

---

## 🛡️ The 5 Essential Security Gates

| Gate # | Name | Tool | Target Scope | Output Report |
| :---: | :--- | :--- | :--- | :--- |
| **1** | Secret Detection | **TruffleHog** | Git repository & filesystem | `gate-01-trufflehog.json` |
| **2** | Python SAST | **Bandit** | `backend/` Python source code | `gate-02-bandit.json` |
| **3** | IaC Security | **Checkov** | `infrastructure/terraform` & `kubernetes` | `gate-03-checkov.json` |
| **4** | Dockerfile Linting | **Hadolint** | `backend/Dockerfile` & `frontend/Dockerfile` | `gate-04-hadolint.json` |
| **5** | DAST Baseline Testing | **OWASP ZAP** | Running app at `http://localhost:8000` | `gate-05-zap.json` & `.html` |

---

## 📁 Directory Structure

```text
security/
├── README.md                          # This documentation manual
├── config/
│   └── security-policy.yaml           # Quality Gate thresholds & enforcement modes
├── framework/
│   ├── five_gates_runner.py           # Unified Python runner engine for all 5 gates
│   ├── seven_gates_runner.py          # Backward-compatibility shim
│   ├── gatekeeper.py                  # Policy gatekeeper & threshold evaluator
│   └── normalizer.py                  # Standard report schema model
├── runners/                           # Individual PowerShell gate runners
│   ├── run-trufflehog.ps1             # Gate 1 runner
│   ├── run-bandit.ps1                 # Gate 2 runner
│   ├── run-checkov.ps1                # Gate 3 runner
│   ├── run-hadolint.ps1               # Gate 4 runner
│   └── run-zap.ps1                    # Gate 5 runner
├── scripts/                           # Multi-gate automation scripts
│   ├── run-all-gates.ps1              # Executes all 5 gates & generates summary
│   ├── run-single-gate.ps1            # Executes specified gate (1-5)
│   ├── security-summary.ps1           # Displays aggregated console summary
│   └── verify_enforcement_negative.py # Boundary & negative policy testing
├── policies/
│   └── security-thresholds.yaml       # Thresholds for STRICT and ADVISORY modes
└── .venv/                             # Isolated scanner Python virtual environment
```

---

## 🚀 Execution Guide

### 1. Run All 5 Security Gates (Sequential)
```powershell
# STRICT mode (fails build if any gate fails or is blocked)
.\security\scripts\run-all-gates.ps1 -Mode STRICT

# ADVISORY mode (logs findings without blocking)
.\security\scripts\run-all-gates.ps1 -Mode ADVISORY
```

### 2. Run Individual Gates
```powershell
.\security\runners\run-trufflehog.ps1 -Mode STRICT
.\security\runners\run-bandit.ps1 -Mode STRICT
.\security\runners\run-checkov.ps1 -Mode STRICT
.\security\runners\run-hadolint.ps1 -Mode STRICT
.\security\runners\run-zap.ps1 -TargetUrl "http://localhost:8000"
```

### 3. Display Executive Security Summary
```powershell
.\security\scripts\security-summary.ps1
```
