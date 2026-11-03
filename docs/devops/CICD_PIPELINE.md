# ArchitectIQ — CI/CD Pipeline Reference & Stage Breakdown

## 1. Overview

The ArchitectIQ CI/CD pipeline is implemented in declarative Jenkins syntax (`Jenkinsfile`). It automates the full lifecycle from code push to Kubernetes deployment across 20 sequential stages with automated safety gates.

---

## 2. 20-Stage Breakdown & Functionality

### Stage 1: Checkout
- Clones the Git repository commit triggered by GitHub webhook or SCM polling.
- Generates build metadata including build number, Git short commit identifier, and unified image tag.

### Stage 2: Environment Verification
- Inspects and verifies the execution environment, installed tooling (Python, Node.js, Docker, Terraform, kubectl), and system dependencies.

### Stage 3: Backend Dependency Installation
- Resolves Python 3.11 production dependencies from `requirements.txt`.
- Verifies that all required packages can be cleanly imported into the runtime environment.

### Stage 4: Backend Tests
- Executes the full backend Pytest automated test suite (122 tests across simulation, optimizer, and chaos engineering).
- Enforces strict quality gate: If any test fails, the pipeline immediately halts.

### Stage 5: Frontend Dependency Installation
- Installs clean dependencies using `package-lock.json` for deterministic resolution.
- Validates integrity of required Node.js build modules.

### Stage 6: Frontend Tests
- Executes the native Node.js unit and regression test suite (13 tests).
- Confirms state lifecycle, API client contracts, and UI gatekeepers.

### Stage 7: Frontend Production Build
- Compiles the production bundle via Vite.
- Verifies existence of `dist/index.html` and `dist/assets`; halts if compilation fails.

### Stage 8: Terraform Format Check
- Checks formatting of all Terraform definitions in `infrastructure/terraform/` using `terraform fmt -check -recursive`.

### Stage 9: Terraform Initialization
- Initializes the Terraform working directory and provider plugins in non-interactive mode.

### Stage 10: Terraform Validation
- Validates syntax and provider schema compatibility of Terraform configurations prior to planning.

### Stage 11: Terraform Plan
- Generates a speculative execution plan using `terraform plan -input=false` without applying changes to state.

### Stage 12: Ansible Validation
- Validates Ansible automation assets in `infrastructure/ansible/`, inspecting inventory definitions, syntax, and task declarations.

### Stage 13: Docker Image Build
- Compiles the backend container image using Python 3.11-slim and the frontend container image using multi-stage Node 20 / Nginx Alpine runtime.
- Tags images with versioned identifier `${BUILD_NUMBER}-${SHORT_COMMIT}` and `latest`.

### Stage 14: Docker Image Verification
- Inspects built Docker images, verifies manifest metadata, image labels, and binary presence.

### Stage 15: Kubernetes Pre-deployment Checks
- Validates cluster connectivity, verifies namespace `architectiq` existence, and checks resource availability before applying manifests.

### Stage 16: Kubernetes Deployment
- Applies Kubernetes manifests (ConfigMaps, Secrets, Deployments, and Services) targeting the `architectiq` namespace.
- Updates deployment images to reference the newly built and verified version tag.

### Stage 17: Kubernetes Rollout Verification
- Monitors rolling deployment status across backend and frontend Deployments with a rollout timeout.

### Stage 18: Application Health Verification
- Queries live container health endpoints inside the cluster:
  - Backend health probe targeting `/health`.
  - Frontend web probe targeting `/healthz`.

### Stage 19: Monitoring Verification
- Verifies Prometheus target accessibility and ensures Prometheus and Grafana monitoring stacks are active and healthy.

### Stage 20: Build Summary
- Assembles a structured summary report containing build status, metadata, commit SHA, image tags, and test results.
- Archives the summary as a persistent build artifact in Jenkins.
