# ArchitectIQ — Kubernetes Orchestration Reference Guide

> [!NOTE]
> In accordance with Project Architectural Rule 1, Kubernetes orchestration is excluded from active deployment in favor of a lean, production-style Docker Compose deployment. The manifests in `infrastructure/kubernetes/` are preserved strictly as declarative Infrastructure-as-Code reference assets.

## 1. Overview

ArchitectIQ is orchestrated on Kubernetes using native resources designed for high availability, zero-downtime rolling updates, and self-healing. The configuration is optimized for local-first execution (e.g. Docker Desktop Kubernetes, Minikube, or Kind) as well as cloud production clusters.

---

## 2. Manifest Inventory (`infrastructure/kubernetes/`)

| Manifest | Kind | Purpose |
| :--- | :--- | :--- |
| `namespace.yaml` | `Namespace` | Creates the isolated `architectiq` namespace. |
| `configmap.yaml` | `ConfigMap` | Non-sensitive runtime variables (`PORT=8000`, `AI_PROVIDER=auto`, etc.). |
| `secrets.example.yaml` | `Secret` | Sensitive API keys (`GEMINI_API_KEY`, `HF_TOKEN`). |
| `backend-deployment.yaml` | `Deployment` | 2 replicas running Python FastAPI + Simulation Engine. |
| `backend-service.yaml` | `Service` | Internal `ClusterIP` exposing port `8000`. |
| `frontend-deployment.yaml` | `Deployment` | 2 replicas running Vite SPA + Nginx. |
| `frontend-service.yaml` | `Service` | `NodePort` service exposing port `80` (NodePort `30080`). |
| `ingress.yaml` | `Ingress` | NGINX Ingress routing `/api` & `/health` to backend, `/` to frontend. |
| `kustomization.yaml` | `Kustomization` | Declarative manifest orchestration and image tag patching. |

---

## 3. High Availability & Resilience Features

- **Replica Redundancy**: Both backend and frontend run with `replicas: 2`.
- **Rolling Updates**: `strategy.type = RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0` ensures zero dropped requests during upgrades.
- **Liveness Probes**:
  - Backend: `GET /health` (Port 8000, initialDelay: 15s, period: 10s).
  - Frontend: `GET /healthz` (Port 80, initialDelay: 10s, period: 10s).
- **Readiness Probes**:
  - Backend: `GET /health` (Port 8000, initialDelay: 5s, period: 5s).
  - Frontend: `GET /healthz` (Port 80, initialDelay: 5s, period: 5s).
- **Resource Constraints**:
  - Backend: Requests 250m CPU / 256Mi RAM; Limits 1000m CPU / 1024Mi RAM.
  - Frontend: Requests 100m CPU / 64Mi RAM; Limits 500m CPU / 256Mi RAM.

---

## 4. Deployment Workflow (Documentation Reference Only)

```bash
kubectl apply -k infrastructure/kubernetes/

kubectl rollout status deployment/architectiq-backend -n architectiq
kubectl rollout status deployment/architectiq-frontend -n architectiq

kubectl get pods -n architectiq -o wide

kubectl get svc -n architectiq
```

