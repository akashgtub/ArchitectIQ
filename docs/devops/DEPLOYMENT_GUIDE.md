# ArchitectIQ — Automated Deployment Guide

## 1. Overview

ArchitectIQ utilizes Docker Compose as its primary, production-grade deployment platform. This architecture provides fast rolling recreation with minimal service interruption (~1–3s during container replacement), automated post-deployment health verification, and immediate automated rollback if an unhealthy state is detected. True zero-downtime rolling cutovers require multi-replica clustering with a dynamic reverse proxy pool.

---

## 2. Pre-Deployment Health Verification

Before triggering a deployment, confirm that the Docker daemon and existing network are healthy:
```powershell
docker ps
```
The active stack contains:
- `architectiq-backend` (FastAPI, Port 8000)
- `architectiq-frontend` (Nginx SPA & Reverse Proxy, Port 80)
- `architectiq-prometheus` (Prometheus, Port 9090)
- `architectiq-grafana` (Grafana, Port 3001)
- `devopsforge-jenkins` (Jenkins Controller, Port 8081)

---

## 3. Automated Deployment Procedure

Execute the deployment script:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy-docker.ps1 -ImageTag <IMAGE_TAG>
```

### Deployment Lifecycle:
1. **State Preservation**: The script reads the currently active image tag from `reports/deployments/last-known-good.json`.
2. **Container Update**: Docker Compose updates backend and frontend containers with the new image tag.
3. **Automated Health Probing**:
   - Backend direct: `http://localhost:8000/health` (HTTP 200 expected)
   - Frontend direct: `http://localhost:80/healthz` (HTTP 200 expected)
   - Frontend reverse proxy: `http://localhost:80/health` (HTTP 200 expected)
4. **Pass Criteria**: If all three endpoints respond healthy within the configured timeout (default: 60s), the deployment succeeds, and the state file is updated.
5. **Fail Criteria**: If any health probe fails or times out, the script triggers `scripts\deploy\rollback-docker.ps1` automatically, reverting the environment to the prior verified state with zero manual intervention.

---

## 4. Continuous Deployment via GitHub Actions & Jenkins

When changes are pushed to `main`:
1. **GitHub Actions** checks out code and contacts Jenkins via REST API.
2. **Jenkins Pipeline** executes 14 sequential stages (linting, testing, container builds, 7 DevSecOps quality gates, and image verification).
3. **Automated Deployment**: Upon Jenkins build success, GitHub Actions executes `scripts\deploy\deploy-docker.ps1` on the self-hosted Windows runner.
4. **Audit Trail**: Every deployment is recorded in `reports/deployments/deployment-history.jsonl` with commit SHA, timestamp, and status.
