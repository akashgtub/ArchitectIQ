# ArchitectIQ — Security & DevSecOps Guide

## 1. DevSecOps Architecture Overview

Security is built directly into every stage of the ArchitectIQ delivery lifecycle. The repository implements a unified, sequential Seven-Gate DevSecOps framework orchestrated by `security/framework/seven_gates_runner.py` and enforced through Jenkins and GitHub Actions.

---

## 2. The Seven DevSecOps Security Gates

| Gate # | Tool | Category | Target / Scope | Verdict Output |
| :---: | :--- | :--- | :--- | :--- |
| **Gate 1** | **TruffleHog** | Secret Detection | Git commit history, configuration files, and staged assets | `PASS` / `FAIL` |
| **Gate 2** | **Bandit** | Python SAST | `backend/` Python source tree (`-r backend -ll -ii`) | `PASS` / `FAIL` |
| **Gate 3** | **Checkov** | IaC Security | `infrastructure/terraform` configuration files | `PASS` / `FAIL` |
| **Gate 4** | **Hadolint** | Dockerfile Linting | `backend/Dockerfile` and `frontend/Dockerfile` | `PASS` / `FAIL` |
| **Gate 5** | **Snyk** | Dependency Vulnerabilities | Cloud SaaS dependency engine using Jenkins `snyk-token` | `PASS` / `BLOCKED` |
| **Gate 6** | **OWASP ZAP** | DAST Probing | Dynamic HTTP security baseline probing on `:8000` | `PASS` / `FAIL` |
| **Gate 7** | **SonarCloud** | Code Quality & SAST | Hosted SonarCloud engine using Jenkins `sonar-token` | `PASS` / `BLOCKED` |

---

## 3. Resource-Safe Execution & Memory Guardrails

To prevent scanner runaway and protect system stability:
1. **Host RAM Guard**: The framework detects total and available system memory across Windows, WSL2, and Linux containers. If available memory drops below `512.0 MB`, scans are safely BLOCKED with clear diagnostic logs.
2. **Individual Timeouts**: Every scanner runs sequentially with isolated process-tree timeouts (30s to 90s). Timed-out processes are immediately terminated with child-process cleanup.
3. **Cloud SaaS Migration**: Snyk (Gate 5) and SonarCloud (Gate 7) run against hosted SaaS free-tier engines, eliminating the ~2.5 GB memory footprint of a local SonarQube container.

---

## 4. Quality Gate Policy Modes

The pipeline supports two deterministic enforcement modes configured via the `SECURITY_ENFORCEMENT_MODE` parameter:

### STRICT Mode (Production & Main Push Standard)
- Halts pipeline execution with exit code 1 if any gate fails.
- If mandatory SaaS credentials (`SNYK_TOKEN`, `SONAR_TOKEN`) are missing, the pipeline truthfully halts with status `BLOCKED`.
- Failure masking is strictly prohibited.

### ADVISORY Mode (Development & Diagnostic Evaluation)
- Executes all available gates sequentially.
- If cloud credentials are not configured, records truthful `BLOCKED` status without failing the pipeline.
- Generates and publishes comprehensive JSON and Markdown summaries in `reports/security/` for developer review.

---

## 5. Secret Handling & Log Protection

1. **Zero Exposure**: Secrets and tokens are injected via environment variables (`withCredentials`) and never passed as command-line arguments, logged to stdout, or included in JSON reports.
2. **Standardized Reports**: Every scan produces an immutable JSON report in `reports/security/gate-XX-<tool>.json` following a unified schema.
3. **Summary Publishing**: In CI/CD runs, `reports/security/security-summary.md` is automatically published directly to GitHub Step Summaries and archived as Jenkins build artifacts.
