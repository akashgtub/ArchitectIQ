# ArchitectIQ — Rollback & Disaster Recovery Guide

## 1. Overview

ArchitectIQ maintains an automated, stateful rollback mechanism powered by `scripts/deploy/rollback-docker.ps1` and state tracking in `reports/deployments/last-known-good.json`.

---

## 2. Automatic Rollback Mechanism

During automated deployments via `scripts/deploy/deploy-docker.ps1`:
- If newly deployed containers fail to pass health checks across `/health` (backend), `/healthz` (frontend), and `/health` (reverse proxy) within 60 seconds, an automatic rollback is immediately initiated.
- The script restores the exact `last-known-good` image tag recorded before the failed deployment.
- Rollback execution and health verification results are appended to `reports/deployments/deployment-history.jsonl` with status `ROLLED_BACK`.

---

## 3. Manual Rollback Execution

If manual rollback is required by an operator:

### Option A: Rollback to Last-Known-Good Tag
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\rollback-docker.ps1
```
The script will inspect `reports/deployments/last-known-good.json` and restore the last successfully verified tag.

### Option B: Rollback to a Specific Historical Tag
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\rollback-docker.ps1 -RollbackTag <SPECIFIC_TAG>
```

---

## 4. Post-Rollback Health Validation

After rollback completes, verify service reachability:
```powershell
# 1. Backend health
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# 2. Frontend health
Invoke-WebRequest -Uri "http://localhost:80/healthz" -UseBasicParsing

# 3. Reverse proxy health
Invoke-WebRequest -Uri "http://localhost:80/health" -UseBasicParsing
```
All three endpoints must return `HTTP 200 OK`.

---

## 5. Volume & Data Protection Guardrails

ArchitectIQ's application containers (`backend`, `frontend`) are entirely stateless. All metrics and dashboard configurations reside in isolated named Docker volumes:
- `architectiq-prometheus-data`
- `architectiq-grafana-data`
- `devopsforge_jenkins_home`

> [!IMPORTANT]
> Rolling back application containers never touches or resets persistent volumes.
