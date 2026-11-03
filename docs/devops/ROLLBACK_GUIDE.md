# ArchitectIQ — Rollback & Recovery Guide

## 1. Overview

ArchitectIQ incorporates automated and manual rollback mechanisms across Kubernetes, Docker, and the Jenkins CI/CD pipeline. This ensures zero data loss and minimal recovery time when deployment failures or regressions occur.

---

## 2. Automated Pipeline Rollback (Stage 12)

When `AUTO_ROLLBACK_ON_FAILURE=true` in Jenkins parameters:

1. Stage 12 executes post-deployment health checks against both backend (`/health`) and frontend (`/healthz`).
2. If either endpoint fails to respond with HTTP 200 within the timeout window, the pipeline initiates an immediate rollback:
   ```bash
   kubectl rollout undo deployment/architectiq-backend -n architectiq
   kubectl rollout undo deployment/architectiq-frontend -n architectiq
   ```
3. Kubernetes immediately terminates the failing new revision pods and restores the previous known-good deployment revision.
4. The pipeline marks the build as failed and logs the incident for investigation.

---

## 3. Manual Kubernetes Rollback Procedures

### 1. View Deployment Rollout History
```bash
kubectl rollout history deployment/architectiq-backend -n architectiq

kubectl rollout history deployment/architectiq-frontend -n architectiq
```

### 2. Rollback to the Immediately Preceding Revision
```bash
kubectl rollout undo deployment/architectiq-backend -n architectiq
kubectl rollout undo deployment/architectiq-frontend -n architectiq
```

### 3. Rollback to a Specific Historical Revision
```bash
kubectl rollout undo deployment/architectiq-backend -n architectiq --to-revision=2

kubectl rollout status deployment/architectiq-backend -n architectiq
```

---

## 4. Docker Compose Rollback

If operating under Docker Compose without Kubernetes:

```bash
export IMAGE_TAG=previous-stable-tag
docker-compose up -d --no-build
```

---

## 5. State Preservation During Rollbacks

Because ArchitectIQ operates in-memory for session investigations (`_INVESTIGATIONS_DB`) and baseline results (`_BASELINE_STORE`) without modifying persistent external databases, rollbacks are safe, atomic, and do not require destructive database schema rollbacks.

