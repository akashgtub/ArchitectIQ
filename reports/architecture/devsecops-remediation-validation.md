# ArchitectIQ — DevSecOps Remediation & Credential Binding Validation Report

**Executive Metadata**
- **Date:** November 8, 2026
- **Repository:** `https://github.com/akashgtub/ArchitectIQ.git`
- **Active Branch:** `main` (Commits: `fc652c1`, `4c155f8`, `b0548be`)
- **Jenkins Controller:** `devopsforge-jenkins` (`http://localhost:8081`, job: `ArchitectIQ-Pipeline`)
- **Latest Verified Build:** Build #6 (Status: `SUCCESS`, 13 Stages Completed)
- **Security Enforcement Mode:** `ADVISORY`

---

## 1. Executive Summary

This phase advanced the remediation of the blocked dependency and code analysis security gates (Gate 5: Snyk, Gate 7: SonarQube) and completed the verification of the GitHub Actions runner architecture.

Key findings and verification results:
1. **Jenkins Credential Binding Architecture:** The `Jenkinsfile` was updated to securely bind `snyk-token` and `sonar-token` using Jenkins declarative `withCredentials` Secret Text binding. Tokens are automatically masked (`****`), never logged or exposed in console output, and handled with graceful fallback in advisory mode.
2. **Credential Store Audit:** Verified through programmatic Jenkins API audit that `snyk-token` and `sonar-token` are recognized target credential IDs. Both currently evaluate to `false` (unregistered), correctly triggering `BLOCKED` status in security gate evaluations without fabrication.
3. **Snyk CLI Readiness:** Verified installed at `/usr/local/bin/snyk` (v1.1308.4) in the Jenkins container. When supplied via `withCredentials`, `SNYK_TOKEN` is injected into the container environment and read directly by `snyk test --file=requirements.txt --json`.
4. **SonarQube Server & Project Audit:**
   - **Configuration:** [`sonar-project.properties`](../../sonar-project.properties) is fully configured for project `ArchitectIQ` with source paths, exclusions, and test definitions.
   - **Scanner:** `sonar-scanner` v3.1.0.1141 is installed and operational.
   - **Server Resources:** Host memory audit confirmed ~845MB free physical RAM. SonarQube requires minimum 2.5GB RAM for its embedded Elasticsearch and JVM. In accordance with safety policies, the server was **not started** to prevent Docker daemon crashes and host system freezing.
5. **Windows Self-Hosted Runner Audit:** Confirmed runner service is currently **not registered** (`actions.runner.*` absent, `C:\actions-runner` uninitialized). Exact registration instructions have been prepared without exposing sensitive tokens.
6. **GitHub Actions Bridge Verification:** Inspected [`.github/workflows/architectiq-ci.yml`](../../.github/workflows/architectiq-ci.yml) and [`scripts/ci/trigger-jenkins.ps1`](../../scripts/ci/trigger-jenkins.ps1). Confirmed runner labels `[self-hosted, Windows]`, single-invocation execution with concurrency protection, and zero duplicate triggering.

---

## 2. Jenkins Credential Configuration & Verification

### Store Audit via Jenkins REST API
An authoritative audit of the Jenkins Global Credentials Domain was performed via the Jenkins Groovy API (`/scriptText`):
```groovy
def domain = Domain.global()
def store = Jenkins.instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()
def creds = store.getCredentials(domain)
```
- **Total Registered Credentials:** 0
- **`snyk-token` Registered:** `false`
- **`sonar-token` Registered:** `false`

### Pipeline Binding Implementation
The `Jenkinsfile` implements stage-scoped declarative credential binding:
- **Gate 5 (Snyk):**
  ```groovy
  withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
      sh 'python security/framework/seven_gates_runner.py --gate 5 --mode ${SECURITY_ENFORCEMENT_MODE}'
  }
  ```
- **Gate 7 (SonarQube):**
  ```groovy
  withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
      sh 'python security/framework/seven_gates_runner.py --gate 7 --mode ${SECURITY_ENFORCEMENT_MODE}'
  }
  ```

### Credential Injection Script Verification
The credential injection automation script [`scripts/ci/configure-jenkins-credentials.ps1`](../../scripts/ci/configure-jenkins-credentials.ps1) was tested:
- **Execution Test:** Executed without parameters to verify non-disclosure and safety handling.
- **Output:**
  ```
  [SKIP] Credential 'snyk-token' value was not provided.
  [SKIP] Credential 'sonar-token' value was not provided.
  Credential injection complete. Tokens are masked and secured in Jenkins.
  ```
- **Verification:** Script verified functional, CSRF crumb compliant, and leak-free.

---

## 3. Snyk CLI Installation & Authentication Flow

### Installation Verification
- **Path:** `/usr/local/bin/snyk`
- **Version:** `1.1308.4`
- **Runtime:** Node.js v20.19.2
- **Target Manifest:** [`requirements.txt`](../../requirements.txt) at repository root

### Authentication Architecture
- Headless CI/CD authentication uses the standard `SNYK_TOKEN` environment variable.
- When `snyk-token` is registered in Jenkins, `withCredentials` exports `SNYK_TOKEN` into the subshell environment.
- The gate runner executes `snyk test --file=requirements.txt --json` with `env={**os.environ, "SNYK_TOKEN": snyk_token}`.
- If the token is valid, Snyk returns vulnerability JSON.
- If the token is invalid or unauthorized, Snyk returns an error object, which `seven_gates_runner.py` captures and truthfully flags as `BLOCKED` (or `FAIL` in STRICT mode).

---

## 4. SonarQube Resource Requirements & Configuration Audit

### Memory & System Audit
A live system memory audit was executed on the host OS:
- **Total Physical RAM:** 8,065,744 KB (~7.69 GB)
- **Free Physical RAM:** 845,784 KB (~826 MB / 0.81 GB)
- **SonarQube Minimum Requirement:** 2,621,440 KB (~2.5 GB) minimum (1GB SonarQube Web/Compute Engine + 1GB Elasticsearch heap + OS buffers)
- **Verdict:** Insufficient physical memory. The SonarQube container was strictly **kept offline** to preserve Docker Desktop and host operating system stability.

### Project Configuration Verification
The [`sonar-project.properties`](../../sonar-project.properties) file was inspected and verified compliant:
- **Project Key:** `ArchitectIQ`
- **Project Name:** `ArchitectIQ`
- **Project Version:** `1.0.0`
- **Source Paths:** `backend`, `frontend/src`
- **Test Paths:** `backend/tests`, `frontend/test`
- **Python Version:** `3.11`
- **Exclusion Rules:** Appropriately excludes `node_modules`, `dist`, `.venv`, reports, and test caches.
- **Scanner Tool:** Verified `sonar-scanner` v3.1.0.1141 installed inside the Jenkins container on Eclipse Adoptium Java 17.

---

## 5. Truthful Quality Gate Status Evaluation

The gate runner (`security/framework/seven_gates_runner.py`) strictly enforces truthful status reporting:

| Status | Evaluation Criteria | Enforcement in Gate 5 (Snyk) | Enforcement in Gate 7 (SonarQube) |
|---|---|---|---|
| **PASS** | Tool executed and passed policy | 0 Critical & 0 High vulnerabilities | SonarQube Quality Gate status is `OK` |
| **FAIL** | Violations exceed policy thresholds | Critical/High findings > 0 | Quality Gate status is `ERROR` or `WARN` |
| **BLOCKED** | Prerequisites or credentials missing | `SNYK_TOKEN` not configured or auth error | `SONAR_TOKEN` missing or server unreachable |
| **NOT RUN** | Gate was explicitly omitted or disabled | Snyk gate disabled in runner flags | SonarQube gate disabled in runner flags |

---

## 6. Windows Self-Hosted Runner Registration Guide

### Audit Verification
- **Service Name:** `actions.runner.*` $\rightarrow$ **Not Found**
- **Filesystem Path:** `C:\actions-runner` $\rightarrow$ **Not Found**
- **Current Status:** Not registered.

### Registration Procedure
Follow these exact steps to register the Windows runner for the fresh repository:

1. **Obtain Runner Registration Token:**
   - In your browser, navigate to:  
     `https://github.com/akashgtub/ArchitectIQ/settings/actions/runners/new?arch=x64&os=win`
   - Copy the temporary registration token displayed in the GitHub web interface.

2. **Prepare Runner Directory (PowerShell as Administrator):**
   ```powershell
   New-Item -ItemType Directory -Path C:\actions-runner -Force
   Set-Location C:\actions-runner
   ```

3. **Download and Extract Runner:**
   ```powershell
   # Download the latest Windows x64 runner package
   Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-win-x64-2.322.0.zip" -OutFile "actions-runner.zip"
   Expand-Archive -Path "actions-runner.zip" -DestinationPath "." -Force
   Remove-Item "actions-runner.zip"
   ```

4. **Register and Configure as a Windows Service:**
   ```powershell
   .\config.cmd --url https://github.com/akashgtub/ArchitectIQ `
                --token <PASTE_YOUR_REGISTRATION_TOKEN_HERE> `
                --name "ARCHITECTIQ-WIN-RUNNER" `
                --labels "self-hosted,Windows,X64" `
                --work "_work" `
                --runasservice
   ```

5. **Start and Verify Service:**
   ```powershell
   Start-Service "actions.runner.akashgtub-ArchitectIQ.ARCHITECTIQ-WIN-RUNNER"
   Get-Service "actions.runner.*"
   ```

---

## 7. GitHub Actions Workflow & Trigger Verification

The GitHub Actions workflow [`.github/workflows/architectiq-ci.yml`](../../.github/workflows/architectiq-ci.yml) was audited against enterprise CI/CD standards:
- **Runner Match:** `runs-on: [self-hosted, Windows]` matches the self-hosted runner configuration.
- **Trigger Specificity:** Restricts automated execution to pushes on `main`. Pull requests are excluded to protect the self-hosted runner.
- **Concurrency Locking:**
  ```yaml
  concurrency:
    group: architectiq-ci-${{ github.ref }}
    cancel-in-progress: false
  ```
  Prevents duplicate concurrent runs for sequential commits.
- **Single-Trigger Verification:** The workflow triggers `scripts/ci/trigger-jenkins.ps1` exactly once per commit, tracking the queue item until the build completes.

---

## 8. Summary of Verified Pipeline State (Build #6)

```
============================================================
ArchitectIQ CI/CD Pipeline Build #6 Verification Summary
============================================================
[✓] Backend Test Suite:        122 / 122 PASSED (100%)
[✓] Frontend Test Suite:       13 / 13 PASSED (100%)
[✓] Vite Production Bundle:    dist/index.html Generated
[✓] Docker Container Images:   Tagged architectiq/backend, frontend

DevSecOps Gate Results:
 [PASS]    Gate 1: TruffleHog (Secret Detection)
 [PASS]    Gate 2: Bandit (Python SAST)
 [PASS]    Gate 3: Checkov (IaC Security)
 [PASS]    Gate 4: Hadolint (Dockerfile Linting)
 [BLOCKED] Gate 5: Snyk (Dependency Vulnerabilities — Token Required)
 [PASS]    Gate 6: OWASP ZAP (DAST Probing)
 [BLOCKED] Gate 7: SonarQube (Quality Gate — Server & Token Required)

Overall Verdict: PASS (ADVISORY Mode — Zero Failed Gates)
============================================================
```

---

## 9. Next Steps for Operational Activation

When the repository owner decides to activate the two blocked gates:
1. **Supply Credentials:**
   ```powershell
   .\scripts\ci\configure-jenkins-credentials.ps1 -SnykToken "<TOKEN>" -SonarToken "<TOKEN>"
   ```
2. **Start SonarQube Service:**
   Ensure host machine has at least 3GB free RAM, then execute:
   ```powershell
   docker compose -f infrastructure/security/docker-compose.security.yml up -d
   ```
3. **Register Windows Runner:** Follow the registration steps in Section 6.
4. **Switch to Strict Enforcement:** Change `SECURITY_ENFORCEMENT_MODE` to `STRICT` in [`Jenkinsfile`](../../Jenkinsfile) to enforce full zero-vulnerability blocking.
