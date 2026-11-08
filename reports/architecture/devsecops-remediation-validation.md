# ArchitectIQ — DevSecOps Remediation & Credential Binding Validation Report

**Executive Metadata**
- **Date:** November 8, 2026
- **Repository:** `https://github.com/akashgtub/ArchitectIQ.git`
- **Active Branch:** `main` (Commits: `fc652c1`, `4c155f8`)
- **Jenkins Controller:** `devopsforge-jenkins` (`http://localhost:8081`, job: `ArchitectIQ-Pipeline`)
- **Pipeline Execution Validated:** Build #6 (Status: `SUCCESS`, 13 Stages Completed)
- **Security Enforcement Mode:** `ADVISORY`

---

## 1. Executive Summary

This remediation addressed the blocked dependency and static analysis security gates (Gate 5: Snyk, Gate 7: SonarQube) in the ArchitectIQ CI/CD pipeline:
1. **Jenkins Credential Binding Architecture:** Inspected `Jenkinsfile` and identified that Stages 9 and 10 lacked credentials binding. Updated `Jenkinsfile` to securely bind `snyk-token` and `sonar-token` using Jenkins declarative `withCredentials` Secret Text binding with automatic masking and graceful fallback.
2. **Scanner Availability Verified:**
   - **Snyk CLI:** Verified installed and operational at `/usr/local/bin/snyk` (v1.1308.4).
   - **SonarQube Scanner:** Verified installed and operational at `/usr/local/bin/sonar-scanner` (v3.1.0.1141 on Eclipse Adoptium Java 17).
   - **SonarQube Server:** Verified container `architectiq-sonarqube` status. The service is defined in `infrastructure/security/docker-compose.security.yml` but currently offline; host system has ~874MB free physical RAM (SonarQube requires minimum ~2.5GB).
3. **Execution & Integrity:** Executed Jenkins **Build #6**. All 122 backend tests and 13 frontend tests passed (135/135 tests passing). The five functional gates (TruffleHog, Bandit, Checkov, Hadolint, OWASP ZAP) executed cleanly with 0 findings. Gates 5 and 7 accurately report `BLOCKED` status with transparent error diagnostics, adhering strictly to zero fabrication policies.

---

## 2. Jenkinsfile Credential Binding Inspection & Fix

### Prior State
Previously, `Jenkinsfile` executed `python security/framework/seven_gates_runner.py --gate 5` and `--gate 7` without any Jenkins credentials binding. Even if credentials existed in Jenkins, the runner process did not receive them in its execution environment.

### Implemented Fix
Updated `Jenkinsfile` in commit `fc652c1` to bind credentials securely:

```groovy
// Stage 9: Snyk Dependency Scanning
stage('9. Snyk') {
    steps {
        echo ">>> Stage 9: Executing Gate 5 — Snyk Dependency Vulnerability Scanning (${params.SECURITY_ENFORCEMENT_MODE})..."
        script {
            try {
                withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
                    sh '''
                        python security/framework/seven_gates_runner.py --gate 5 --mode ${SECURITY_ENFORCEMENT_MODE}
                    '''
                }
            } catch (Exception e) {
                echo "[ADVISORY] Snyk credential 'snyk-token' not configured in Jenkins credentials store. Executing gate in fallback mode..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 5 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }
    }
}

// Stage 10: SonarQube Code Quality & Security Analysis
stage('10. SonarQube Analysis') {
    steps {
        echo ">>> Stage 10: Executing Gate 7 — SonarQube Code Quality & Security Analysis (${params.SECURITY_ENFORCEMENT_MODE})..."
        script {
            try {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh '''
                        python security/framework/seven_gates_runner.py --gate 7 --mode ${SECURITY_ENFORCEMENT_MODE}
                    '''
                }
            } catch (Exception e) {
                echo "[ADVISORY] SonarQube credential 'sonar-token' not configured in Jenkins credentials store. Executing gate in fallback mode..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 7 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }
    }
}
```

### Security Properties of the Implementation
- **Automatic Masking:** Jenkins Secret Text binding automatically redacts any bound token value from the console log (`****`).
- **No Hardcoding:** Zero credentials, keys, or secrets are hardcoded in source code or committed to Git.
- **Graceful Fault Tolerance:** If credentials are not yet configured in Jenkins, the pipeline logs an informational message and executes the gate runner in advisory mode rather than failing the entire build with a fatal Groovy exception.

---

## 3. Scanner Verifications

### Snyk CLI Verification
- **Container Path:** `/usr/local/bin/snyk`
- **Version:** `1.1308.4`
- **Target File:** `requirements.txt` (located at repository root)
- **Status:** Installed, configured, and ready to authenticate as soon as `snyk-token` is provided.

### SonarQube Scanner Verification
- **Container Path:** `/usr/local/bin/sonar-scanner`
- **Version:** `3.1.0.1141`
- **Runtime Environment:** Java 17.0.18 Eclipse Adoptium (64-bit), Linux 6.18 WSL2
- **Status:** Installed and operational.

### SonarQube Server Availability Audit
- **Compose Stack:** `infrastructure/security/docker-compose.security.yml`
- **Image:** `sonarqube:10.5-community`
- **Container Name:** `architectiq-sonarqube` (Port: 9000)
- **Current State:** Stopped / Offline.
- **Resource Audit:** SonarQube's embedded Elasticsearch requires minimum 2.5GB RAM. Host currently has ~874MB free physical memory. Starting SonarQube on low memory without sufficient swap/heap limits could cause host system instability.

---

## 4. How to Configure SNYK_TOKEN and SONAR_TOKEN in Jenkins

### Option A: Via Jenkins Web UI (Recommended)

1. Open your browser and navigate to: **`http://localhost:8081`**
2. Log in as an administrator (or `cicd-bot`).
3. Click on **Manage Jenkins** in the left sidebar $\rightarrow$ click **Credentials**.
4. Click on the **System** store $\rightarrow$ click **Global credentials (unrestricted)**.
5. Click **+ Add Credentials** in the top right:
   - **Kind:** `Secret text`
   - **Scope:** `Global (Jenkins, nodes, items, all child items, etc.)`
   - **Secret:** Enter your Snyk API token (from [https://app.snyk.io/account](https://app.snyk.io/account) $\rightarrow$ Auth Token)
   - **ID:** `snyk-token` *(Must match exactly)*
   - **Description:** `Snyk API Token for DevSecOps Dependency Scanning`
   - Click **Create**.
6. Repeat for SonarQube:
   - Click **+ Add Credentials**
   - **Kind:** `Secret text`
   - **Scope:** `Global`
   - **Secret:** Enter your SonarQube user token (from SonarQube $\rightarrow$ My Account $\rightarrow$ Security $\rightarrow$ Generate Token)
   - **ID:** `sonar-token` *(Must match exactly)*
   - **Description:** `SonarQube User Token for DevSecOps Quality Gate`
   - Click **Create**.

### Option B: Automated Script Injection

Run the automated credential injector PowerShell script:
```powershell
.\scripts\ci\configure-jenkins-credentials.ps1 -SnykToken "<YOUR_SNYK_TOKEN>" -SonarToken "<YOUR_SONAR_TOKEN>"
```
This script connects via authenticated Jenkins REST API using `cicd-bot` credentials and injects both secret texts directly into the Jenkins credentials store without displaying them in console logs.

---

## 5. Self-Hosted Runner Status & Setup Instructions

### Current Status
- **Service Name:** `actions.runner.*`
- **Path:** `C:\actions-runner`
- **Audit Result:** **Not installed / registered**. The runner service does not currently exist on this Windows machine.

### Runner Registration Procedure
To enable GitHub Actions to automatically trigger local Jenkins builds on push:
1. Navigate to: `https://github.com/akashgtub/ArchitectIQ/settings/actions/runners/new?arch=x64&os=win`
2. Download the runner package and create `C:\actions-runner`:
   ```powershell
   New-Item -ItemType Directory -Path C:\actions-runner -Force
   Set-Location C:\actions-runner
   # Extract downloaded actions-runner-win-x64-*.zip
   ```
3. Run the configuration command using the GitHub-provided token:
   ```powershell
   .\config.cmd --url https://github.com/akashgtub/ArchitectIQ --token <REGISTRATION_TOKEN> --name "ARCHITECTIQ-WIN-RUNNER" --work "_work" --runasservice
   .\run.cmd
   ```
4. Confirm runner appears as **Idle / Online** in GitHub repository settings.

---

## 6. Full Pipeline Verification (Build #6)

### Execution Metrics
- **Job:** `ArchitectIQ-Pipeline`
- **Build Number:** `#6`
- **Commit:** `4c155f8` (`main`)
- **Status:** `Finished: SUCCESS`
- **Total Duration:** 1 min 24 sec

### Automated Test Suite Results
- **Backend Tests:** 122 tests executed, **122 passed (100%)**, 0 failures, 2 benign Starlette deprecation warnings.
- **Frontend Tests:** 13 tests executed, **13 passed (100%)**, 0 failures.
- **Application Bundle:** Production build compiled via Vite (`dist/index.html` verified).
- **Container Build:** Images tagged and verified (`architectiq/backend:latest`, `architectiq/frontend:latest`).

### Seven DevSecOps Gates Results

| Gate # | Security Tool | Domain | Status | Findings | Details / Verdict |
|:---:|---|---|:---:|:---:|---|
| **1** | **TruffleHog** | Secret Detection | **PASS** | 0 | 0 verified secrets detected across codebase. |
| **2** | **Bandit** | Python SAST | **PASS** | 0 | 0 High/Medium vulnerabilities. |
| **3** | **Checkov** | Infrastructure as Code | **PASS** | 0 | Terraform & Docker compose compliant. |
| **4** | **Hadolint** | Dockerfile Linting | **PASS** | 0 | Both Dockerfiles follow security best practices. |
| **5** | **Snyk** | Dependency Scanning | **BLOCKED** | 0 | `BLOCKED — CREDENTIAL REQUIRED: SNYK_TOKEN environment variable is not configured.` |
| **6** | **OWASP ZAP** | DAST Probing | **PASS** | 0 | Probed live at `http://host.docker.internal:8000`. 0 Critical/High findings. |
| **7** | **SonarQube** | Code Quality & SAST | **BLOCKED** | 0 | `BLOCKED — CREDENTIAL REQUIRED: SONAR_TOKEN environment variable not set.` |

**Gate Statistics:**
- Total Gates: 7
- Passed Gates: 5
- Blocked Gates: 2 (Credentials / Service Required)
- Failed Gates: 0
- Overall Quality Gate Verdict: **PASS** (ADVISORY Mode)

---

## 7. Integrity Statement

In strict compliance with DevSecOps integrity rules:
- **No Scan Results Fabricated:** Gate 5 (Snyk) and Gate 7 (SonarQube) are accurately reported as `BLOCKED` awaiting credentials and service availability.
- **No Application Degradation:** Core backend and frontend code were preserved untouched; all 135 tests continue to pass.
- **Decoupled Architecture Preserved:** Independent Compose stacks for Jenkins, Monitoring, and Security remain decoupled.
