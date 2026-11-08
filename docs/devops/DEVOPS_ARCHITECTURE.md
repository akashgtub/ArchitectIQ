# ArchitectIQ — DevOps Architecture Overview

## 1. System Vision & Objective

ArchitectIQ is an AI-powered System Design Optimization and Resilience platform. It performs multimodal architecture diagram understanding, graph topology validation, workload-driven discrete-event simulations, deterministic Pareto optimization, and chaos engineering fault injections.

This document describes the end-to-end DevOps architecture built around the application to enable automated continuous integration, security validation, containerization, deployment orchestration, configuration management, and observability.

---

## 2. Integrated Toolchain Architecture

The DevOps architecture is intentionally unified so that each tool fulfills a clear, dedicated responsibility:

```text
GitHub (Source Control)
   │
   ▼
Jenkins (CI/CD Pipeline Orchestrator)
   ├── Stage 1: Checkout
   ├── Stage 2: Environment Verification
   ├── Stage 3: Backend Dependency Installation
   ├── Stage 4: Backend Tests (122 Pytest Cases)
   ├── Stage 5: Frontend Dependency Installation
   ├── Stage 6: Frontend Tests (13 Node.js Tests)
   ├── Stage 7: Frontend Production Build (Vite)
   ├── Stage 8: Terraform Format Check
   ├── Stage 9: Terraform Initialization
   ├── Stage 10: Terraform Validation
   ├── Stage 11: Terraform Plan
   ├── Stage 12: Ansible Validation
   ├── Stage 13: Docker Image Build
   ├── Stage 14: Docker Image Verification
   ├── Stage 15: Kubernetes Pre-deployment Checks
   ├── Stage 16: Kubernetes Deployment
   ├── Stage 17: Kubernetes Rollout Verification
   ├── Stage 18: Application Health Verification
   ├── Stage 19: Monitoring Verification
   └── Stage 20: Build Summary
   │
   ▼
Docker (Containerization)
   ├── Backend: Python 3.11-slim, Uvicorn, Non-root user (Port 8000)
   └── Frontend: Multi-stage Node 20-alpine builder + Nginx 1.25 runtime (Port 80)
   │
   ▼
Terraform (Infrastructure as Code)
   └── Provisions Kubernetes namespaces, ConfigMaps, and cluster baseline
   │
   ▼
Ansible (Configuration Management)
   └── Prepares deployment environments, mounts, templates, and runtime readiness
   │
   ▼
Kubernetes (Workload Orchestration)
   ├── Namespace: architectiq
   ├── Deployments: architectiq-backend (2 replicas), architectiq-frontend (2 replicas)
   ├── Services: backend (ClusterIP:8000), frontend (NodePort:30080)
   └── Ingress: NGINX Ingress routing /api and /health to backend, / to frontend
   │
   ▼
Monitoring & Observability
   ├── Prometheus: Health probes scraping backend (/health) and frontend (/healthz)
   └── Grafana: Automated dashboards visualizing availability, latency, and uptime
```

---

## 3. Separation of Responsibilities

| Tool | Core Responsibility | Artifacts / Locations |
| :--- | :--- | :--- |
| **GitHub** | Source version control, branch protection, pull requests, webhook dispatch. | Repository root |
| **Jenkins** | End-to-end pipeline coordination, test gating, image tagging, deployment triggering. | `Jenkinsfile` |
| **Docker** | Encapsulated, immutable application runtimes for backend and frontend. | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` |
| **Terraform** | Declarative creation of Kubernetes namespaces, base ConfigMaps, and cluster-level primitives. | `infrastructure/terraform/` |
| **Ansible** | Environment validation, OS-level directory setup, runtime readiness, and template rendering. | `infrastructure/ansible/` |
| **Kubernetes**| Workload scheduling, self-healing, health probing, zero-downtime rolling updates. | `infrastructure/kubernetes/` |
| **Prometheus**| Time-series metric collection and active service endpoint health probing. | `infrastructure/monitoring/prometheus/` |
| **Grafana** | Centralized dashboard visualization and service uptime tracking. | `infrastructure/monitoring/grafana/` |

---

## 4. End-to-End Workflow Walkthrough

1. **Push**: A developer pushes a commit or opens a pull request to GitHub.
2. **Trigger**: GitHub triggers the Jenkins pipeline via webhook or SCM polling.
3. **CI Validation**:
   - Backend tests run against Python 3.11 with 122 automated tests.
   - Frontend tests run using Node.js native test runner (`node --test`), followed by `vite build`.
4. **Infrastructure & Configuration Verification**: Terraform formats, initializes, validates, and plans; Ansible validates inventory and playbooks.
5. **Image Build & Tagging**: Images are built, tagged with `${BUILD_NUMBER}-${SHORT_COMMIT}`, and verified.
6. **Kubernetes Deployment**: Kubernetes applies manifests, updates pod image tags, and verifies rollout readiness.
7. **Health Verification**: Kubernetes probes confirm `/health` and `/healthz`.
8. **Observability**: Prometheus continuously polls service metrics and Grafana displays operational metrics.

