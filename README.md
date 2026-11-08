# ArchitectIQ — Enterprise DevOps & DevSecOps Platform

ArchitectIQ is an end-to-end autonomous AI system engineering platform. It ingests system architecture diagrams, validates graph topologies, executes workload-driven discrete-event simulations, discovers performance bottlenecks via AI root-cause analysis, synthesizes alternative candidate architectures through deterministic multi-objective optimization, and stresses systems using chaos engineering resilience experiments.

This repository features an enterprise-grade, modular, five-component architecture that strictly isolates the application runtime, DevOps infrastructure, monitoring observability, DevSecOps security automation (7 Essential Tools), and CI/CD pipelines.

---

## 🏛️ Enterprise Five-Component Architecture

The platform is partitioned into five independently manageable components that interact strictly through defined network interfaces and APIs without cross-layer coupling:

```
+-------------------------------------------------------------------------------+
|                           ArchitectIQ Enterprise Platform                     |
+-------------------------------------------------------------------------------+
| [Component A] Application Runtime                                             |
|   - Backend: FastAPI (Python 3.11, discrete simulation & optimization)        |
|   - Frontend: Vite-compiled SPA + Nginx reverse proxy                         |
|   - Root Compose: docker-compose.yml (Ports 80, 8000)                         |
|   - Architecture: In-Memory State, zero external DB dependencies              |
+-------------------------------------------------------------------------------+
| [Component B] DevOps Infrastructure                                           |
|   - Infrastructure as Code: infrastructure/terraform/                         |
|   - Container Orchestration: infrastructure/kubernetes/                       |
|   - Configuration Automation: infrastructure/ansible/                         |
|   - Jenkins CI/CD Controller: infrastructure/jenkins/                         |
|   - Independent SonarQube Service: infrastructure/security/                   |
+-------------------------------------------------------------------------------+
| [Component C] Monitoring & Observability Stack                                |
|   - Prometheus: Metric scraping & storage (Port 9090)                         |
|   - Grafana: Metric visualization & alert dashboards (Port 3001)              |
|   - Compose: infrastructure/monitoring/docker-compose.monitoring.yml          |
+-------------------------------------------------------------------------------+
| [Component D] DevSecOps Security Framework (7 Essential Tools)                |
|   - 7 Security Gates: TruffleHog, Bandit, Checkov, Hadolint, Snyk, ZAP, Sonar |
|   - Isolated Python Virtualenv: security/.venv                                |
|   - Runners: security/runners/run-*.ps1                                       |
|   - Standardized Output: reports/security/gate-01 through 07.json             |
+-------------------------------------------------------------------------------+
| [Component E] CI/CD Pipeline Automation                                       |
|   - Jenkinsfile: 13-stage enterprise pipeline with zero failure masking       |
|   - Jenkins Controller Container: devopsforge-jenkins (Port 8081)             |
+-------------------------------------------------------------------------------+
```

---

## 🚀 Quick Start: Central Batch Launcher

The platform is managed through a central, path-independent Windows Batch script:

```cmd
start-architectiq.bat
```

The launcher provides an interactive 31-option console menu covering all platform operations:

```text
============================================================================
                     ARCHITECTIQ PLATFORM LAUNCHER                         
              Enterprise DevOps, CI/CD, and DevSecOps Suite                
============================================================================

  [ APPLICATION (FRONTEND + BACKEND) ]
    1. Start Application
    2. Stop Application
    3. Restart Application
    4. Application Status and Health
    5. Open Application UI in Browser (http://localhost)

  [ DEVOPS INFRASTRUCTURE ]
    6. Start DevOps Infrastructure (Monitoring + Jenkins)
    7. Stop DevOps Infrastructure
    8. DevOps Infrastructure Status

  [ MONITORING and OBSERVABILITY ]
    9. Start Monitoring Stack (Prometheus + Grafana)
   10. Stop Monitoring Stack
   11. Monitoring Stack Status
   12. Open Prometheus in Browser (http://localhost:9090)
   13. Open Grafana in Browser (http://localhost:3001)

  [ CI/CD AUTOMATION (JENKINS) ]
   14. Start Jenkins Controller
   15. Stop Jenkins Controller
   16. Jenkins Status
   17. Open Jenkins in Browser (http://localhost:8081)

  [ DEVSECOPS SECURITY FRAMEWORK (7 ESSENTIAL TOOLS) ]
   18. Start Security Tools (SonarQube)
   19. Stop Security Tools (SonarQube)
   20. Run All 7 Security Scans
   21. Run Individual Security Scan (Gate 1 - 7)
   22. Run SonarQube Analysis
   23. Run OWASP ZAP against Local Test Environment
   24. View Security Reports
   25. Display Security Status and Summary

  [ PLATFORM and CONFIG VALIDATION ]
   26. Validate Docker Configurations
   27. Validate Terraform IaC Configurations
   28. Validate Kubernetes Manifests
   29. Validate Ansible Playbooks

  [ COMPREHENSIVE AUDIT and EXIT ]
   30. Check All Platform Components and Endpoints
   31. Exit
```

---

## 📁 Repository Directory Structure

```text
ArchitectIQ/
├── backend/                                   # Component A: FastAPI Application
│   ├── ai_agent/                              # Multi-modal architecture ingestion & extraction
│   ├── api/                                   # REST API endpoints & schemas
│   ├── chaos_lab/                             # Chaos engineering & failure simulator
│   ├── optimizer/                             # Architecture candidate generator & optimizer
│   ├── simulator/                             # Discrete-event performance simulation engine
│   ├── shared/                                # Canonical data contracts and adapters
│   ├── tests/                                 # 122 automated backend pytest unit & integration tests
│   ├── config.py                              # Application configuration
│   ├── Dockerfile                             # Multi-stage security-hardened backend image
│   └── main.py                                # FastAPI app entrypoint
├── frontend/                                  # Component A: Single-Page Application (SPA)
│   ├── src/                                   # UI logic, state manager, design system
│   ├── test/                                  # 13 automated frontend unit tests
│   ├── Dockerfile                             # Multi-stage Nginx-based frontend image
│   ├── nginx.conf                             # Reverse proxy & security header config
│   ├── package.json                           # Node.js dependencies
│   └── vite.config.js                         # Vite build configuration
├── docker-compose.yml                         # Component A: Application Compose (Backend + Frontend ONLY)
├── infrastructure/                            # Component B & C: DevOps Infrastructure
│   ├── ansible/                               # Component B: Ansible playbooks, roles & inventories
│   │   ├── inventory/                         # Host inventory configurations
│   │   ├── playbooks/                         # Playbooks for provisioning, deployment, monitoring
│   │   └── roles/                             # Modular Ansible tasks
│   ├── jenkins/                               # Component E: Jenkins CI/CD Controller
│   │   └── docker-compose.jenkins.yml         # Jenkins Docker Compose stack (Port 8081, 50000)
│   ├── kubernetes/                            # Component B: K8s manifests & Kustomize
│   │   ├── backend-deployment.yaml            # Backend deployment spec
│   │   ├── frontend-deployment.yaml           # Frontend deployment spec
│   │   ├── kustomization.yaml                 # Kustomize manifest bundle
│   │   └── namespace.yaml                     # Dedicated 'architectiq' namespace
│   ├── monitoring/                            # Component C: Monitoring & Observability Stack
│   │   ├── docker-compose.monitoring.yml      # Decoupled Prometheus & Grafana stack
│   │   ├── grafana/                           # Grafana datasource & dashboard provisioning
│   │   └── prometheus/                        # Prometheus scrape configuration
│   ├── security/                              # Component B: Independent Security Services
│   │   └── docker-compose.security.yml        # Independent SonarQube service (Port 9000)
│   └── terraform/                             # Component B: Infrastructure as Code
│       ├── environments/                      # Environment configs (local, aws, production)
│       └── modules/                           # Reusable Terraform modules
├── security/                                  # Component D: DevSecOps Automation Framework
│   ├── .venv/                                 # Isolated virtualenv for scanner dependencies
│   ├── config/                                # Policy thresholds & configuration
│   │   └── security-policy.yaml               # Gatekeeper thresholds & enforcement rules
│   ├── framework/                             # Security runner engine
│   │   ├── seven_gates_runner.py              # Unified engine for 7 essential security tools
│   │   ├── gatekeeper.py                      # Policy compliance evaluator
│   │   └── normalizer.py                      # Standardized report model
│   ├── runners/                               # Individual PowerShell gate runners
│   │   ├── run-trufflehog.ps1                 # Gate 1 runner
│   │   ├── run-bandit.ps1                     # Gate 2 runner
│   │   ├── run-checkov.ps1                    # Gate 3 runner
│   │   ├── run-hadolint.ps1                   # Gate 4 runner
│   │   ├── run-snyk.ps1                       # Gate 5 runner
│   │   ├── run-zap.ps1                        # Gate 6 runner
│   │   └── run-sonarqube.ps1                  # Gate 7 runner
│   ├── scripts/                               # Multi-gate automation scripts
│   │   ├── run-all-gates.ps1                  # Runs all 7 gates and aggregates summary
│   │   ├── run-single-gate.ps1                # Runs specified gate (1-7)
│   │   └── security-summary.ps1               # Displays aggregated console summary
│   ├── reports/
│   │   └── .gitkeep                           # Git tracking anchor
│   └── README.md                              # Dedicated security manual
├── scripts/                                   # Platform Automation Scripts
│   ├── application/                           # start-app, stop-app, restart-app, app-status
│   ├── infrastructure/                        # start-devops, stop-devops, devops-status
│   ├── monitoring/                            # start-monitoring, stop-monitoring, monitoring-status
│   ├── jenkins/                               # start-jenkins, stop-jenkins, jenkins-status
│   ├── security/                              # start-security, stop-security, view-reports
│   ├── validation/                            # validate-docker, validate-terraform, validate-k8s, validate-ansible
│   └── health/                                # check-all-services
├── reports/                                   # DevSecOps JSON reports & HTML artifacts
│   └── security/                              # gate-01 through gate-07 reports & security-summary
├── sonar-project.properties                   # SonarQube project analysis configuration
├── Jenkinsfile                                # Component E: 13-Stage Enterprise CI/CD Pipeline
├── start-architectiq.bat                      # Path-independent 31-option Windows Batch Launcher
├── pytest.ini                                 # Pytest configuration
├── requirements.txt                           # Backend Python dependencies
└── README.md                                  # Enterprise architecture and operations manual
```

---

## 🌐 Port & Service Reference

| Service | Container Name | Port | Description | Health Check |
| :--- | :--- | :---: | :--- | :--- |
| **Frontend UI** | `architectiq-frontend` | `80` | Web Dashboard & Reverse Proxy | `GET http://localhost/healthz` |
| **Backend API** | `architectiq-backend` | `8000` | FastAPI Simulation & Optimization | `GET http://localhost:8000/health` |
| **Prometheus** | `architectiq-prometheus`| `9090` | Metrics Collection & TSDB | `GET http://localhost:9090/-/healthy` |
| **Grafana** | `architectiq-grafana` | `3001` | Dashboards & Visualizations | `GET http://localhost:3001/api/health` |
| **Jenkins** | `devopsforge-jenkins` | `8081` | CI/CD Controller | `GET http://localhost:8081/login` |
| **Jenkins Agent**| `devopsforge-jenkins` | `50000`| JNLP Inbound Agent Port | Port listener |
| **SonarQube** | `architectiq-sonarqube`| `9000` | Code Quality & Security Server | `GET http://localhost:9000/api/system/status` |
| **Kubernetes API**| `desktop-control-plane`| `6443` | Local Kubernetes Control Plane | `kubectl cluster-info` |

---

## 🛡️ DevSecOps 7 Essential Security Tools

The framework integrates seven essential security tools with standardized reports in `reports/security/gate-0X-<tool>.json`:

| Gate # | Name | Tool / Mechanism | Scope | Report File |
| :---: | :--- | :--- | :--- | :--- |
| **1** | Secret Detection | **TruffleHog** | Git repository and working tree secret leaks | `gate-01-trufflehog.json` |
| **2** | Python SAST | **Bandit** | AST-based security scanning of `backend/` | `gate-02-bandit.json` |
| **3** | IaC Security | **Checkov** | Terraform and Kubernetes misconfiguration scanning | `gate-03-checkov.json` |
| **4** | Dockerfile Linting | **Hadolint** | Backend and frontend Dockerfile best practices | `gate-04-hadolint.json` |
| **5** | Dependency Scanning | **Snyk** | Python & npm dependency vulnerabilities | `gate-05-snyk.json` |
| **6** | DAST Baseline Scan | **OWASP ZAP** | Dynamic application testing of `http://localhost:8000` | `gate-06-zap.json` & `.html` |
| **7** | Quality & Security | **SonarQube** | Static analysis & Quality Gate evaluation | `gate-07-sonarqube.json` |

### Running Security Scans
```powershell
# Run all 7 security gates (STRICT mode blocks on policy failures)
.\security\scripts\run-all-gates.ps1 -Mode STRICT

# Run all 7 security gates in ADVISORY mode (audits without failing)
.\security\scripts\run-all-gates.ps1 -Mode ADVISORY

# Run an individual gate (e.g. Gate 2: Bandit)
.\security\runners\run-bandit.ps1 -Mode STRICT

# View aggregated security reports
.\security\scripts\security-summary.ps1
```

---

## 🔄 CI/CD Pipeline (`Jenkinsfile`)

The enterprise Jenkins pipeline executes 13 dedicated stages with zero command masking or artificial test bypassing:

1. **Checkout**: Repository retrieval and commit metadata resolution.
2. **Backend Tests**: 122 automated pytest unit and integration tests with JUnit reporting.
3. **Frontend Tests**: 13 automated Vitest/Node client and lifecycle regression tests.
4. **Application Build**: Vite compilation into production distribution and Docker image builds.
5. **TruffleHog (Gate 1)**: Git commit and filesystem secret scanning.
6. **Bandit (Gate 2)**: Python backend static application security testing.
7. **Checkov (Gate 3)**: Infrastructure as Code security evaluation for Terraform and Kubernetes.
8. **Hadolint (Gate 4)**: Dockerfile security and syntax linting.
9. **Snyk (Gate 5)**: Dependency vulnerability scanning for pip and npm packages.
10. **SonarQube Analysis (Gate 7)**: Static code analysis execution via SonarScanner.
11. **SonarQube Quality Gate (Gate 7)**: Project status validation against configured Quality Gate.
12. **OWASP ZAP Baseline Scan (Gate 6)**: Dynamic baseline probing of local endpoints.
13. **Security Report Aggregation**: Generation of `security-summary.json` and artifact archiving.

---

## 🧪 Testing & Verification

### Run Backend Pytest Suite (122 Tests)
```powershell
pytest
```
*Expected: 122 passed in ~158s*

### Run Frontend Unit Tests (13 Tests)
```powershell
npm --prefix frontend test
```
*Expected: 13 passed in ~15s*

### Run Platform Validation Suite
```powershell
.\scripts\validate-project.ps1
```
Runs validation across Docker Compose, Terraform syntax, Kubernetes manifests (dry-run), and Ansible YAML playbooks.

### Run Comprehensive Platform Health Check
```powershell
.\scripts\health\check-all-services.ps1
```
*Expected: 6 of 6 platform components HEALTHY*

---

## ⚠️ Architectural Isolation Rules & Policies

1. **No External Database**: ArchitectIQ uses fast, optimized in-memory state models. No external database (Postgres, MySQL, Mongo) is required or started.
2. **Application Isolation**: Monitoring tools, Jenkins agents, and security scanners are NEVER packaged inside application Docker images (`architectiq-backend` or `architectiq-frontend`).
3. **Decoupled Lifecycle**: Starting the application (`docker-compose.yml` or Option 1) starts ONLY frontend and backend. Monitoring, Jenkins, and SonarQube do NOT start automatically.
4. **Volume Preservation**: Data volumes (`architectiq-prometheus-data`, `architectiq-grafana-data`, `devopsforge_jenkins_home`, `architectiq-sonarqube-data`) are persistent and preserved across container restarts.
5. **No Cloud Resource Modification**: The platform executes local validation and dry-runs; no cloud resources or paid infrastructure are created or destroyed.
