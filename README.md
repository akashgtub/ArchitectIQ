# ArchitectIQ — Enterprise DevOps, DevSecOps & AI Architecture Engineering Platform

[![CI/CD Bridge](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions%20%2B%20Jenkins-blue?style=flat-square&logo=jenkins)](https://github.com/akashgtub/ArchitectIQ)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%28Python%203.11%29-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Docker](https://img.shields.io/badge/Containers-Docker%20Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com)
[![DevSecOps](https://img.shields.io/badge/Security-7%20Automated%20Gates-red?style=flat-square&logo=owasp)](security/)
[![Prometheus](https://img.shields.io/badge/Metrics-Prometheus%20Time--Series-E6522C?style=flat-square&logo=prometheus)](http://localhost:9090)
[![Grafana](https://img.shields.io/badge/Observability-Grafana%20Dashboards-F46800?style=flat-square&logo=grafana)](http://localhost:3001)
[![Terraform](https://img.shields.io/badge/IaC-Terraform%20v1.5%2B-7B42BC?style=flat-square&logo=terraform)](https://www.terraform.io)
[![Ansible](https://img.shields.io/badge/Automation-Ansible%20Playbooks-EE0000?style=flat-square&logo=ansible)](infrastructure/ansible/)

**ArchitectIQ** is an enterprise-grade AI system design simulation and optimization engine. It ingests system architecture diagrams, transforms them into directed NetworkX graph topologies, simulates discrete-event workloads under dynamic traffic patterns, discovers performance bottlenecks through AI root-cause analysis, synthesizes Pareto-optimal candidate architectures via multi-objective genetic algorithms (NSGA-II), and validates system resilience using chaos fault-injection experiments.

The platform is designed around a **stateless, in-memory execution architecture** requiring zero external SQL/NoSQL databases, backed by an automated CI/CD pipeline, continuous observability, and a 7-gate DevSecOps framework.

---

## 🏛️ System & DevOps Architecture

```
                                      [ Code Push / Webhook ]
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  GitHub Actions Runner │
                                    │ (ARCHITECTIQ-WIN-RUNNER│
                                    └────────────┬───────────┘
                                                 │ Authenticated REST API (trigger-jenkins.ps1)
                                                 ▼
                                    ┌────────────────────────┐
                                    │ Jenkins Controller CI  │
                                    │ (devopsforge-jenkins)  │
                                    └────────────┬───────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
        ┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
        │  Automated Testing   │      │ DevSecOps 7 Gates    │      │ Image Packaging      │
        │ - Pytest (122 tests) │      │ - TruffleHog (Sec)   │      │ - Multi-stage Build  │
        │ - Vitest (13 tests)  │      │ - Bandit (Python)    │      │ - Docker Image Tag   │
        │ - Total: 135/135 Pass│      │ - Checkov (IaC)      │      │ - Manifest Archive   │
        │                      │      │ - Hadolint (Docker)  │      │                      │
        │                      │      │ - OWASP ZAP (DAST)   │      │                      │
        └──────────────────────┘      └──────────────────────┘      └──────────────────────┘
                                                 │
                                                 ▼ (On Pipeline SUCCESS)
                                    ┌────────────────────────┐
                                    │ Minimal-Downtime Deploy│
                                    │ (deploy-docker.ps1)    │
                                    └────────────┬───────────┘
                                                 │ Rolling Update & Health Probing (:8000, :80)
                                                 ▼ (If Unhealthy: rollback-docker.ps1)
                         ┌───────────────────────────────────────┐
                         │       Production Docker Network       │
                         │         (architectiq-network)         │
                         │                                       │
                         │  ┌─────────────────┐ ┌──────────────┐ │
                         │  │ Nginx Frontend  │ │ FastAPI App  │ │
                         │  │ (Port 80)       │ │ (Port 8000)  │ │
                         │  └────────┬────────┘ └──────┬───────┘ │
                         └───────────┼─────────────────┼─────────┘
                                     │                 │ Scrape /metrics
                                     ▼                 ▼
                         ┌───────────────────────────────────────┐
                         │     Monitoring & Observability        │
                         │                                       │
                         │  ┌─────────────────┐ ┌──────────────┐ │
                         │  │ Prometheus TSDB │ │ Grafana UI   │ │
                         │  │ (Port 9090)     │ │ (Port 3001)  │ │
                         │  └─────────────────┘ └──────────────┘ │
                         └───────────────────────────────────────┘
```

---

## ⚡ Key DevOps & DevSecOps Capabilities

1. **Stateless In-Memory Architecture**: High-speed SimPy discrete-event simulation and NetworkX graph traversal with zero external database dependencies.
2. **Automated Deployment & Health Probing**: One-click deployment script (`scripts/deploy/deploy-docker.ps1`) with progressive health checks across backend, frontend, and reverse proxy. Single-instance Docker Compose recreation incurs a brief ~1–3s cutover interruption.
3. **Automated Rollback Guard**: If containers fail health checks within 60 seconds, `scripts/deploy/rollback-docker.ps1` immediately restores the last verified stable image tag recorded in `reports/deployments/last-known-good.json`.
4. **Hybrid CI/CD Orchestration**: GitHub Actions on Windows self-hosted runner triggers Jenkins via authenticated REST API, streams progressive build logs, retrieves security summaries, and deploys containers.
5. **Five-Gate DevSecOps Framework**: Standardized scanning across secrets (TruffleHog), code quality (Bandit), IaC misconfigurations (Checkov), Dockerfile linting (Hadolint), and DAST baseline probing (OWASP ZAP).
6. **Resource-Safe Memory Guard**: Scanners dynamically inspect system RAM across Windows and Linux. Execution is guarded below `512.0 MB` with strict 30s-90s timeouts to prevent runaway processes.
7. **Production Observability**: Native Prometheus metric exposition (`/metrics`) collecting latency histograms and HTTP status codes, mapped to automated Grafana monitoring dashboards.

---

## 🌐 Port Matrix & Service Endpoints

| Port | Service | Container | Ingress URL | Health Check URL | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **80** | Nginx Web Frontend | `architectiq-frontend` | `http://localhost` | `http://localhost/healthz` | **UP** |
| **8000** | FastAPI Application Backend | `architectiq-backend` | `http://localhost:8000` | `http://localhost:8000/health` | **UP** |
| **3001** | Grafana Dashboard UI | `architectiq-grafana` | `http://localhost:3001` | `http://localhost:3001/api/health` | **UP** |
| **9090** | Prometheus Server | `architectiq-prometheus` | `http://localhost:9090` | `http://localhost:9090/-/healthy` | **UP** |
| **8081** | Jenkins CI/CD Controller | `devopsforge-jenkins` | `http://localhost:8081` | `http://localhost:8081/login` | **UP** |

---

## 🚀 Quick Start Guide

### 1. Run Automated Production Deployment
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy-docker.ps1 -ImageTag latest
```

### 2. Manual Rollback to Last-Known-Good Tag
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\rollback-docker.ps1
```

### 3. Run DevSecOps Security Gate Suite
```powershell
# Advisory mode: Audits all gates and publishes summary without blocking
python security\framework\five_gates_runner.py --mode ADVISORY

# Strict mode: Enforces quality gates; blocks on any policy failure
python security\framework\five_gates_runner.py --mode STRICT

# View summary report
python security\framework\five_gates_runner.py --summary
```

### 4. Run Test Suites
```powershell
# Backend automated test suite (122 tests)
pytest backend/tests/ -q

# Frontend unit & regression suite (13 tests)
npm --prefix frontend test
```

---

## 🛡️ DevSecOps Five Essential Security Gates

| Gate # | Scanner Tool | Target Scope | Output Artifact | Policy Verdict |
| :---: | :--- | :--- | :--- | :---: |
| **1** | **TruffleHog** | Git commit history and working tree leaks | `reports/security/gate-01-trufflehog.json` | **`PASS`** |
| **2** | **Bandit** | Python AST security analysis (`backend/`) | `reports/security/gate-02-bandit.json` | **`PASS`** |
| **3** | **Checkov** | Infrastructure-as-Code (`infrastructure/terraform`) | `reports/security/gate-03-checkov.json` | **`PASS`** |
| **4** | **Hadolint** | Backend and frontend Dockerfiles | `reports/security/gate-04-hadolint.json` | **`PASS`** |
| **5** | **OWASP ZAP** | Baseline HTTP DAST probing against `:8000` | `reports/security/gate-05-zap.json` | **`PASS`** |

*Note: In `STRICT` mode, any failure or blocked scanner safely halts the CI/CD pipeline before release. In `ADVISORY` mode, findings are logged comprehensively without blocking deployment.*

---

## 📚 Complete Documentation Suite

- **[System Architecture Specification](docs/ARCHITECTURE.md)**: Deep dive into the SimPy engine, graph models, and Docker network topology.
- **[REST API Reference Guide](docs/API_DOCUMENTATION.md)**: Schemas, payload examples, and responses for all simulation and optimization endpoints.
- **[SRE & Operations Runbook](docs/RUNBOOK.md)**: Standard operating procedures for health probing, debugging, log streaming, and disaster recovery.
- **[Automated Deployment Guide](docs/devops/DEPLOYMENT_GUIDE.md)**: Step-by-step rolling deployment and health verification.
- **[Rollback & Recovery Guide](docs/devops/ROLLBACK_GUIDE.md)**: Stateful rollback procedures and volume protection.
- **[Security & DevSecOps Guide](docs/devops/SECURITY_GUIDE.md)**: Five gates, memory guardrails, and compliance enforcement.
- **[CI/CD Pipeline Architecture](docs/devops/CICD_PIPELINE.md)**: Complete 15-stage Jenkins pipeline breakdown and GitHub Actions integration.
- **[Troubleshooting Decision Tree](docs/devops/TROUBLESHOOTING.md)**: Diagnostic flowcharts and solutions for common operational issues.
- **[Troubleshooting Decision Tree](docs/devops/TROUBLESHOOTING.md)**: Diagnostic flowcharts and solutions for common operational issues.
