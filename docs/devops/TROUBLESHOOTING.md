# ArchitectIQ — DevOps Troubleshooting Guide

## 1. Quick Diagnostic Flowchart

```text
Issue Detected
   │
   ├─► Build Failure (Jenkins Stage 4 or 6)
   │     └─► Review Pytest / Node test output; verify Python 3.11 / Node 20 runtime.
   │
   ├─► Infrastructure Validation Failure (Jenkins Stage 8-12)
   │     └─► Review Terraform fmt/validate or Ansible syntax check logs.
   │
   ├─► Container Fails Healthcheck
   │     └─► Inspect backend logs: uvicorn startup errors, missing port, or CORS issues.
   │
   ├─► Kubernetes Rollout Timeout
   │     └─► Check pod status: CrashLoopBackOff, ImagePullBackOff, or OOMKilled.
   │
   └─► Frontend Cannot Reach Backend
         └─► Verify Nginx proxy pass to backend:8000 and service DNS resolution.
```

---

## 2. Common Scenarios & Resolutions

### Scenario 1: Backend Pods in `CrashLoopBackOff`
- **Symptom**: Kubernetes shows backend pods failing to start.
- **Root Causes**:
  - Missing Python module or import failure.
  - Invalid environment variable configuration.
- **Diagnostic Procedure**:
  - Inspect pod standard output and error streams in the Kubernetes namespace.
  - Inspect pod event timelines for failed probes or termination signals.
- **Resolution**:
  - Confirm `PYTHONPATH=/app` is set in the container environment.
  - Verify that `PORT=8000` is defined and matches the readiness probe.

### Scenario 2: Frontend Build Artifacts Missing
- **Symptom**: Jenkins build fails in Stage 7 with missing `dist/index.html`.
- **Root Cause**: Vite production build failed due to syntax error or missing asset.
- **Resolution**:
  - Review the Vite compilation error log in Jenkins console.
  - Run frontend tests locally to identify broken components or syntax errors.

### Scenario 3: `ERR_FRONTEND_NOT_BUILT` on Startup
- **Symptom**: Accessing backend root `/` returns HTTP 503 `ERR_FRONTEND_NOT_BUILT`.
- **Root Cause**: The frontend production build assets were not found in `frontend/dist`.
- **Resolution**:
  - When running via Docker, ensure you are accessing the frontend container on port 80, which compiles and serves static assets directly via Nginx.
  - When running standalone backend locally, compile the frontend bundle first using the build script.

### Scenario 4: Nginx 502 Bad Gateway on Frontend
- **Symptom**: Frontend loads, but API requests return `502 Bad Gateway`.
- **Root Cause**: Nginx cannot connect to the backend upstream on `backend:8000`.
- **Resolution**:
  - Confirm the backend service is healthy and reachable over the Docker bridge network `architectiq-net` or Kubernetes DNS `backend.architectiq.svc.cluster.local`.
  - In Kubernetes, verify that the `backend` service selector matches `app.kubernetes.io/name: architectiq-backend`.
