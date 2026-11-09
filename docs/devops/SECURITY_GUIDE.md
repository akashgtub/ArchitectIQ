# ArchitectIQ — Security & DevSecOps Guide

## 1. DevSecOps Architecture Overview

Security is built directly into every stage of the ArchitectIQ delivery lifecycle. The repository implements a unified, sequential Five-Gate DevSecOps framework orchestrated by `security/framework/five_gates_runner.py` and enforced through Jenkins and GitHub Actions.

---

## 2. The Five DevSecOps Security Gates

| Gate # | Tool | Category | Target / Scope | Verdict Output |
| :---: | :--- | :--- | :--- | :--- |
| **Gate 1** | **TruffleHog** | Secret Detection | Git commit history, configuration files, and staged assets | `PASS` / `FAIL` |
| **Gate 2** | **Bandit** | Python SAST | `backend/` Python source tree (`-r backend -ll -ii`) | `PASS` / `FAIL` |
| **Gate 3** | **Checkov** | IaC Security | `infrastructure/terraform` configuration files | `PASS` / `FAIL` |
| **Gate 4** | **Hadolint** | Dockerfile Linting | `backend/Dockerfile` and `frontend/Dockerfile` | `PASS` / `FAIL` |
| **Gate 5** | **OWASP ZAP** | DAST Probing | Dynamic HTTP security baseline probing on `:8000` | `PASS` / `FAIL` |

---

## 3. Resource-Safe Execution & Memory Guardrails

To prevent scanner runaway and protect system stability:
1. **Host RAM Guard**: The framework detects total and available system memory across Windows, WSL2, and Linux containers. If available memory drops below `512.0 MB`, scans are safely BLOCKED with clear diagnostic logs.
2. **Individual Timeouts**: Every scanner runs sequentially with isolated process-tree timeouts (30s to 90s). Timed-out processes are immediately terminated with child-process cleanup.
3. **Decoupled Architecture**: Scanners run sequentially with independent diagnostic reporting; zero local server RAM overhead.

---

## 4. Quality Gate Policy Modes

The pipeline supports two deterministic enforcement modes configured via the `SECURITY_ENFORCEMENT_MODE` parameter:

### STRICT Mode (Production & Main Push Standard)
- Halts pipeline execution with exit code 1 if any of the five mandatory gates fails or is blocked.
- Authorizes release and deployment only when all five gates report PASS.
- Failure masking is strictly prohibited.

### ADVISORY Mode (Development & Diagnostic Evaluation)
- Executes all 5 gates sequentially.
- Accurately logs all findings, failures, and blocked gates without halting pipeline execution.
- Generates and publishes comprehensive JSON and Markdown summaries in `reports/security/` for developer review.

---

## 5. Secret Handling & Log Protection

1. **Zero Exposure**: Secrets and tokens are injected via environment variables (`withCredentials`) and never passed as command-line arguments, logged to stdout, or included in JSON reports.
2. **Standardized Reports**: Every scan produces an immutable JSON report in `reports/security/gate-XX-<tool>.json` following a unified schema.
3. **Summary Publishing**: In CI/CD runs, `reports/security/security-summary.md` is automatically published directly to GitHub Step Summaries and archived as Jenkins build artifacts.
