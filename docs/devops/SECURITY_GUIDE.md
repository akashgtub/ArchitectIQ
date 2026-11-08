# ArchitectIQ — Security & DevSecOps Guide

## 1. Security Architecture Overview

Security is integrated into every stage of the ArchitectIQ software lifecycle, implementing defense-in-depth across source code, dependencies, container images, cluster orchestration, and secrets management.

---

## 2. Dependency & Image Hardening

ArchitectIQ enforces security throughout the delivery pipeline via pinned dependencies, multi-stage minimal container images, and strict validation.

### Hardening Measures
1. **Dependency Pinning & Verification**:
   - Explicit version pinning in `requirements.txt` and deterministic package locking via `frontend/package-lock.json`.
   - Continuous dependency validation in automated CI test stages.
2. **Container Image Hardening**:
   - Python backend built on minimal `python:3.11-slim` base, eliminating unnecessary system packages and build utilities.
   - Frontend built via multi-stage Node build and served with lightweight `nginx:1.25-alpine`.
   - Containers run with non-root user permissions.

---

## 3. Secret Management & Non-Exposure

- **Zero Hardcoded Secrets**: No API keys, passwords, or tokens are committed to source control.
- **Git Ignore Safeguards**: `.gitignore` and `.dockerignore` strictly ignore `.env`, `.env.*`, `*.key`, `*.pem`, `*.tfstate`, and Ansible vault files.
- **Example Templates**: Safe templates (`.env.example` and `infrastructure/kubernetes/secrets.example.yaml`) provide structured placeholders.
- **Jenkins Credential Masking**: Secrets are injected at runtime via Jenkins `withCredentials`, ensuring tokens never appear in console build logs.
- **Kubernetes Secrets**: Sensitive keys (`GEMINI_API_KEY`, `HF_TOKEN`) are injected into pods using Kubernetes `Secret` objects.

---

## 4. Least-Privilege Container Hardening

1. **Non-Root Execution**:
   - Backend container runs as unprivileged user `appuser` (UID `10001:10001`).
   - Root privilege escalation is explicitly blocked in Kubernetes security context:
     ```yaml
     securityContext:
       allowPrivilegeEscalation: false
       runAsNonRoot: true
       runAsUser: 10001
     ```
2. **Capability Dropping**:
   - Container processes drop all Linux capabilities (`drop: ["ALL"]`).
3. **Read-Only Root Filesystem**:
   - Containers are configured to restrict write operations except for explicit temporary volumes.

