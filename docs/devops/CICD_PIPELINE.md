# ArchitectIQ — CI/CD Pipeline Architecture & Stage Reference

## 1. Overview

ArchitectIQ implements an enterprise hybrid CI/CD pipeline combining **GitHub Actions** on a Windows self-hosted runner (`ARCHITECTIQ-WIN-RUNNER`) and **Jenkins** in Docker (`devopsforge-jenkins`).

```
[ Push to main / Manual Dispatch ]
                 │
                 ▼
     [ GitHub Actions Workflow ]
  (Runs on ARCHITECTIQ-WIN-RUNNER)
                 │
                 ▼
[ scripts/ci/trigger-jenkins.ps1 ]
  - Service Account: cicd-bot
  - CSRF Crumb Acquisition
  - POST /job/ArchitectIQ-Pipeline/buildWithParameters
                 │
                 ▼
     [ Jenkins Declarative Pipeline ]
  (14 Sequential Stages & DevSecOps Gates)
                 │
                 ▼
  [ Artifact Download & Summary Publishing ]
  (reports/security/security-summary.md -> GitHub Step Summary)
                 │
                 ▼
  [ Automated Docker Compose Deployment ]
  (scripts/deploy/deploy-docker.ps1)
  - Rolling container update (~1-3s minimal recreation cutover)
  - Automated health probing (:8000, :80, reverse proxy)
  - Instant automated rollback guard (rollback-docker.ps1)
```

---

## 2. Jenkins Pipeline 15-Stage Breakdown

| Stage # | Stage Name | Operations & Guardrails |
| :---: | :--- | :--- |
| **1** | **Checkout** | Clones trusted source from Git SCM (`refs/heads/main`). |
| **2** | **Build Metadata** | Extracts short commit SHA, sets displayName (`#<BUILD_NUMBER>-<SHORT_COMMIT>`), and validates build tag. |
| **3** | **Backend Tests** | Executes 122 Pytest automated tests covering simulation, optimizer, and chaos engines (`--junitxml`). |
| **4** | **Frontend Tests** | Executes 13 Node unit and regression tests confirming state lifecycle and UI gatekeepers, plus `npm audit`. |
| **5** | **Application Build** | Compiles Vite production bundle (`frontend/dist`) and builds Docker images using BuildKit (`DOCKER_BUILDKIT=1`). |
| **6** | **TruffleHog (Gate 1)** | Scans repository and history for committed secrets, credentials, and API keys. |
| **7** | **Bandit (Gate 2)** | Executes Python AST static security analysis on `backend/` source tree. |
| **8** | **Checkov (Gate 3)** | Scans Infrastructure-as-Code definitions in `infrastructure/terraform/` for cloud security misconfigurations. |
| **9** | **Hadolint (Gate 4)** | Lints backend and frontend Dockerfiles against container security best practices. |
| **10** | **OWASP ZAP (Gate 5)** | Performs automated baseline DAST probing against the local backend endpoint (`:8000`). |
| **11** | **Security Policy Evaluation** | Aggregates 5 gate reports into `security-summary.json` and evaluates STRICT vs ADVISORY mode; archives artifacts. |
| **12** | **Docker Image Verification** | Inspects built container images, validates metadata, and generates `reports/deployments/build-manifest-${IMAGE_TAG}.json`. |
| **13** | **Deployment Approval** | Automatically approves non-production; requires explicit interactive sign-off for production. |
| **14** | **Deployment** | Records release to `last-known-good.json` and appends to `deployment-history.jsonl`. |
| **15** | **Health Checks** | Verifies live application and observability endpoints (`/health`, `/healthz`, reverse proxy). |

---

## 3. GitHub Actions Bridge Script (`trigger-jenkins.ps1`)

The PowerShell bridge script coordinates communication between the self-hosted runner and the Jenkins controller:
- **Authentication**: Authenticates using the `cicd-bot` service account and API token.
- **CSRF Crumb Protection**: Automatically requests and injects the Jenkins CSRF crumb header (`Jenkins-Crumb`).
- **Log Streaming**: Progressively streams live console logs from Jenkins directly to the GitHub Actions workflow terminal.
- **Artifact Retrieval**: Downloads archived DevSecOps reports (`security-summary.md` and `security-summary.json`) via authenticated REST calls.
- **Step Summary**: Renders the complete security gate report table in the GitHub Actions Actions tab.
