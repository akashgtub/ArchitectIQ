# ArchitectIQ DevSecOps Security Framework (7 Essential Tools)

This directory contains the independent DevSecOps security automation framework for ArchitectIQ, incorporating seven industry-standard security tools across static, dynamic, infrastructure, and dependency security analysis.

---

## 🏛️ Architecture & Component Isolation

In alignment with the enterprise platform design:
- **Application Isolation**: The application runtime (`docker-compose.yml`) contains **zero** security scanners or external dependencies.
- **Independent Virtual Environment**: Python scanners (Bandit, Checkov) run inside `security/.venv`, strictly isolated from the backend's FastAPI runtime dependencies.
- **Independent SonarQube Service**: SonarQube runs via its own compose specification (`infrastructure/security/docker-compose.security.yml`).
- **Standardized Reports**: All tools output standardized machine-readable JSON to `reports/security/gate-0X-<tool>.json` and human-readable summaries to `reports/security/security-summary.md`.

---

## 🛡️ The 7 Essential Security Gates

| Gate # | Name | Tool | Target Scope | Output Report |
| :---: | :--- | :--- | :--- | :--- |
| **1** | Secret Detection | **TruffleHog** | Git repository & filesystem | `gate-01-trufflehog.json` |
| **2** | Python SAST | **Bandit** | `backend/` Python source code | `gate-02-bandit.json` |
| **3** | IaC Security | **Checkov** | `infrastructure/terraform` & `kubernetes` | `gate-03-checkov.json` |
| **4** | Dockerfile Linting | **Hadolint** | `backend/Dockerfile` & `frontend/Dockerfile` | `gate-04-hadolint.json` |
| **5** | Dependency Scanning | **Snyk** | `requirements.txt` & `package.json` | `gate-05-snyk.json` |
| **6** | DAST Baseline Testing | **OWASP ZAP** | Running app at `http://localhost:8000` | `gate-06-zap.json` & `.html` |
| **7** | Quality & Security | **SonarQube** | Full repository & Quality Gate | `gate-07-sonarqube.json` |

---

## 📁 Directory Structure

```text
security/
├── README.md                          # This documentation manual
├── config/
│   └── security-policy.yaml           # Quality Gate thresholds & enforcement modes
├── framework/
│   ├── seven_gates_runner.py          # Unified Python runner engine for all 7 gates
│   ├── gatekeeper.py                  # Policy gatekeeper & threshold evaluator
│   └── normalizer.py                  # Standard report schema model
├── runners/                           # Individual PowerShell gate runners
│   ├── run-trufflehog.ps1             # Gate 1 runner
│   ├── run-bandit.ps1                 # Gate 2 runner
│   ├── run-checkov.ps1                # Gate 3 runner
│   ├── run-hadolint.ps1               # Gate 4 runner
│   ├── run-snyk.ps1                   # Gate 5 runner
│   ├── run-zap.ps1                    # Gate 6 runner
│   └── run-sonarqube.ps1              # Gate 7 runner
├── scripts/                           # Multi-gate automation scripts
│   ├── run-all-gates.ps1              # Executes all 7 gates & generates summary
│   ├── run-single-gate.ps1            # Executes specified gate (1-7)
│   └── security-summary.ps1           # Displays aggregated console summary
├── reports/
│   └── .gitkeep                       # Git tracking anchor for reports
└── .venv/                             # Isolated scanner Python virtual environment
```

---

## 🔑 Credential & Environment Variable Configuration

| Variable | Required For | Description | Default |
| :--- | :--- | :--- | :--- |
| `SNYK_TOKEN` | Gate 5 (Snyk) | Snyk API authentication token | None (Reports `BLOCKED` if missing) |
| `SONAR_TOKEN` | Gate 7 (SonarQube) | SonarQube User / Project analysis token | None (Reports `BLOCKED` if missing) |
| `SONAR_HOST_URL` | Gate 7 (SonarQube) | SonarQube Server URL | `http://localhost:9000` |

> [!NOTE]
> When `SNYK_TOKEN` or `SONAR_TOKEN` are not provided, the security framework honestly reports **`BLOCKED — CREDENTIAL REQUIRED`**. It never fabricates success or silently skips scans.

---

## 🚀 Execution Guide

### 1. Run All 7 Security Gates
```powershell
# Strict mode (blocks/fails on any high/critical finding or blocked credential)
.\security\scripts\run-all-gates.ps1 -Mode STRICT

# Advisory mode (executes all gates and logs findings without failing pipeline)
.\security\scripts\run-all-gates.ps1 -Mode ADVISORY
```

### 2. Run Individual Security Gates
```powershell
# Gate 1: TruffleHog Secret Detection
.\security\runners\run-trufflehog.ps1 -Mode STRICT

# Gate 2: Bandit Python SAST
.\security\runners\run-bandit.ps1 -Mode STRICT

# Gate 3: Checkov Infrastructure as Code
.\security\runners\run-checkov.ps1 -Mode STRICT

# Gate 4: Hadolint Dockerfile Linting
.\security\runners\run-hadolint.ps1 -Mode STRICT

# Gate 5: Snyk Dependency Vulnerability Scan
$env:SNYK_TOKEN = "your-snyk-token"
.\security\runners\run-snyk.ps1 -Mode STRICT

# Gate 6: OWASP ZAP DAST Baseline Probing
# Note: Ensure application is running at http://localhost:8000 first
.\security\runners\run-zap.ps1 -TargetUrl "http://localhost:8000"

# Gate 7: SonarQube Code Quality & Security Scan
$env:SONAR_TOKEN = "your-sonar-token"
.\security\runners\run-sonarqube.ps1 -Mode STRICT
```

### 3. View Security Summary
```powershell
.\security\scripts\security-summary.ps1
```

---

## 🐳 SonarQube Service Management

SonarQube runs as an independent service in [infrastructure/security/docker-compose.security.yml](file:///C:/ArchitectIQ/infrastructure/security/docker-compose.security.yml).

### Resource Requirements
- **Memory**: Minimum **2.5 GB RAM** required (Elasticsearch JVM requirements).
- **Disk**: ~1 GB for images and persistent search indices.
- **Port**: `9000`

### Starting SonarQube
```powershell
docker compose -f infrastructure/security/docker-compose.security.yml up -d
```
Access the web dashboard at [http://localhost:9000](http://localhost:9000) (default credentials: `admin` / `admin`).

### Stopping SonarQube
```powershell
docker compose -f infrastructure/security/docker-compose.security.yml stop
```
Data volumes (`architectiq-sonarqube-data`, `architectiq-sonarqube-extensions`, `architectiq-sonarqube-logs`) are preserved.

---

## 📊 Standardized Report Specification

Every gate generates a JSON file adhering to the common schema:

```json
{
  "gate_id": "gate-02-bandit",
  "gate_number": 2,
  "tool_name": "bandit",
  "timestamp": "2026-11-07T09:49:36.123456+00:00",
  "execution_status": "PASS",
  "severity_verdict": "PASS",
  "findings_count": 2,
  "critical_findings": 0,
  "high_findings": 0,
  "medium_findings": 1,
  "low_findings": 1,
  "report_location": "C:\\ArchitectIQ\\reports\\security\\gate-02-bandit.json",
  "error_details": null,
  "findings": [...]
}
```

Standard Statuses:
- **`PASS`**: Tool executed and findings satisfy configured thresholds.
- **`FAIL`**: Tool executed and identified findings exceeding policy limits.
- **`BLOCKED`**: Prerequisites missing (credentials not provided, test app offline, server unreachable).
- **`NOT INSTALLED`**: Tool CLI or binary is not present on the host environment.
- **`NOT RUN`**: Gate has not been invoked.
- **`ERROR`**: Scanner crashed or encountered unhandled execution exceptions.

