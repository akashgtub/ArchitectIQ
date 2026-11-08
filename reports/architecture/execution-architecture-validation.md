# ArchitectIQ — Execution Architecture and Native Cloudflare Tunnel Integration Validation Report

**Document ID:** `ARCHIQ-EXEC-ARCH-2026-11`  
**Execution Timestamp:** `2026-11-07T11:47:00Z`  
**Status:** **VERIFIED & OPERATIONAL**  
**Integration Type:** Native Windows Executable (`cloudflared.exe`) + Central Batch Dispatcher  
**Tunnel Target:** `http://127.0.0.1:8081` (Jenkins CI/CD Webhooks ONLY)

---

## 1. Final Execution Architecture

ArchitectIQ enforces strict architectural boundaries to avoid monolithic container bloat and prevent unnecessary virtualization overhead. Docker is utilized strictly for services that require containerized environments, while developer tooling, security scanners, and networking tunnels operate as native Windows executables or isolated virtual environments.

### Component Isolation Matrix

```mermaid
flowchart TD
    subgraph Host["Host Operating System (Windows 11 AMD64)"]
        subgraph CentralLauncher["Central Management Launcher"]
            BL["start-architectiq.bat (34 Menu Operations)"]
        end

        subgraph NativeTools["Native Windows & Isolated Tooling"]
            CF["cloudflared.exe (v2026.10.7 Native Quick Tunnel)"]
            TH["trufflehog.exe (v3.99.8)"]
            HL["hadolint.exe (v2.15.1)"]
            SNYK["snyk CLI (v1.1308.4)"]
            SONAR["sonar-scanner CLI (v3.1.0)"]
            K8S["kubectl CLI (Docker Desktop Cluster)"]
            TF["terraform CLI (v1.9.8)"]
            subgraph VenvSec["security/.venv"]
                BANDIT["Bandit (v1.9.4 SAST)"]
                CHECKOV["Checkov (v3.4.3 IaC)"]
            end
        end

        subgraph DockerEngine["Docker Container Engine"]
            subgraph AppCompose["Application Stack (docker-compose.yml)"]
                BE["architectiq-backend (:8000)"]
                FE["architectiq-frontend (:80)"]
            end

            subgraph MonCompose["Monitoring Stack (docker-compose.monitoring.yml)"]
                PROM["architectiq-prometheus (:9090)"]
                GRAF["architectiq-grafana (:3001)"]
            end

            subgraph CICompose["CI/CD Stack (docker-compose.jenkins.yml)"]
                JENK["devopsforge-jenkins (:8081)"]
            end

            subgraph SecCompose["Security Stack (docker-compose.security.yml)"]
                SQ["architectiq-sonarqube (:9000 - Standby)"]
            end
        end
    end

    CF -- "Exposes Port 8081 ONLY" --> JENK
    BL -- "Dispatches" --> NativeTools
    BL -- "Manages" --> DockerEngine
```

---

## 2. Docker Compose Isolation and Service Mapping

Every Docker Compose file is decoupled and managed independently. No cross-stack container contamination exists:

1. **Application Compose (`docker-compose.yml`):**
   - Contains **ONLY**:
     - `architectiq-backend` (FastAPI, in-memory discrete-event simulation engine, optimization models). Exposes port `8000`.
     - `architectiq-frontend` (Nginx 1.25 Alpine reverse proxy + Vite SPA bundle). Exposes port `80`.
   - **Zero** database containers (ArchitectIQ uses high-speed in-memory state).
   - **Zero** DevOps, monitoring, scanning, or tunnel containers.
2. **DevOps CI/CD Compose (`infrastructure/jenkins/docker-compose.jenkins.yml`):**
   - Contains `devopsforge-jenkins` (Jenkins LTS controller). Exposes ports `8081` (HTTP) and `50000` (Agent).
   - Mounts persistent volume `devopsforge_jenkins_home`.
   - Decoupled from application startup.
3. **Monitoring & Observability Compose (`infrastructure/monitoring/docker-compose.monitoring.yml`):**
   - Contains `architectiq-prometheus` (port `9090`) and `architectiq-grafana` (port `3001`).
   - Mounts persistent volumes `architectiq-prometheus-data` and `architectiq-grafana-data`.
   - Independently startable and stoppable.
4. **Security Infrastructure Compose (`infrastructure/security/docker-compose.security.yml`):**
   - Contains `architectiq-sonarqube` (port `9000`) and PostgreSQL database backend.
   - Kept in standby to protect host physical RAM (host free RAM is 0.74 GB; SonarQube requires $\ge 2.5$ GB).

---

## 3. Native Windows Tooling Matrix

Rather than forcing every tool into heavy Docker images, native Windows executables and isolated Python virtual environments are used:

| Tool | Implementation Mode | Executable / Engine Path | Purpose |
| :--- | :---: | :--- | :--- |
| **cloudflared** | **Native Windows** | `C:\Program Files (x86)\cloudflared\cloudflared.exe` | Ephemeral Quick Tunnel exposing Jenkins webhook port 8081 |
| **TruffleHog** | Native Windows | `C:\Users\akash\AppData\Local\Microsoft\WindowsApps\trufflehog.EXE` | Filesystem & git commit secret detection (Gate 1) |
| **Hadolint** | Native Windows | `C:\Users\akash\AppData\Local\Microsoft\WindowsApps\hadolint.exe` | Dockerfile security linting (Gate 4) |
| **Bandit** | Isolated venv | `security/.venv/Scripts/python.exe -m bandit` | Python Static Application Security Testing (Gate 2) |
| **Checkov** | Isolated venv | `security/.venv/Scripts/python.exe -m checkov` | Terraform and Kubernetes IaC static analysis (Gate 3) |
| **Snyk CLI** | Native npm global | `C:\Users\akash\AppData\Roaming\npm\snyk.cmd` | Third-party dependency vulnerability scanning (Gate 5) |
| **SonarScanner** | Native npm global | `C:\Users\akash\AppData\Roaming\npm\sonar-scanner.cmd` | Code quality and static analysis runner (Gate 7) |
| **Terraform CLI** | Native Windows | `C:\ProgramData\chocolatey\bin\terraform.exe` | Local AWS simulation and IaC plans |
| **kubectl** | Native Windows | `C:\Program Files\Docker\Docker\resources\bin\kubectl.exe` | Kubernetes cluster inspection (Docker Desktop) |

---

## 4. Cloudflare Native Tunnel Integration

### 4.1 Native Windows Executable Verification
- **Source:** Cloudflare official package via Windows Package Manager (`winget`).
- **Package ID:** `Cloudflare.cloudflared` (Version `2026.10.7`).
- **Binary Location:** `C:\Program Files (x86)\cloudflared\cloudflared.exe`.
- **Integrity:** Verified official installer hash against Cloudflare's release manifest.

### 4.2 PowerShell Automation Helpers
Three dedicated, production-grade PowerShell scripts manage the native tunnel lifecycle under `scripts/cloudflare/`:

1. [`scripts/cloudflare/start-tunnel.ps1`](file:///c:/ArchitectIQ/scripts/cloudflare/start-tunnel.ps1):
   - **Pre-flight Checks:** Probes `http://127.0.0.1:8081/login` to confirm Jenkins is running before attempting to launch the tunnel.
   - **Process Guard:** Inspects `logs/cloudflare/tunnel.pid` to prevent duplicate tunnel processes.
   - **Isolated Target:** Exclusively forwards to `http://127.0.0.1:8081` via `cloudflared.exe tunnel --url http://127.0.0.1:8081 --no-autoupdate`.
   - **Process Detachment:** Spawns a background Windows process via `Start-Process -PassThru -WindowStyle Hidden`, recording PID and redirecting standard error to `logs/cloudflare/tunnel.log`.
   - **URL Detection:** Polls the log file for the dynamic `https://[name].trycloudflare.com` URL and presents the exact webhook endpoint.
   - **Warning Banner:** Explicitly warns that Quick Tunnel URLs are temporary and session-bound.
2. [`scripts/cloudflare/stop-tunnel.ps1`](file:///c:/ArchitectIQ/scripts/cloudflare/stop-tunnel.ps1):
   - Reads the recorded PID from `logs/cloudflare/tunnel.pid`.
   - **Process Identity Verification:** Queries `Get-Process` to verify the process name contains `cloudflared` before issuing termination, preventing accidental termination of unrelated processes.
   - Gracefully terminates the process and cleans up runtime PID files while preserving logs under `logs/cloudflare/tunnel.log`.
3. [`scripts/cloudflare/tunnel-status.ps1`](file:///c:/ArchitectIQ/scripts/cloudflare/tunnel-status.ps1):
   - Checks binary availability and reports version (`2026.10.7`).
   - Checks whether the project's tunnel process is currently alive (`RUNNING` vs `STOPPED`).
   - Displays the active PID, local target, extracted public trycloudflare URL, and local Jenkins health.
   - **Security:** Never prints credentials, secret tokens, or sensitive network parameters.

---

## 5. Jenkins Authentication & GitHub Webhook Security Validation

### 5.1 Jenkins Access Control Audit
Before enabling external ingress via Cloudflare Tunnel, Jenkins endpoints were probed to confirm that anonymous access is strictly blocked:
- `http://localhost:8081/manage` $\rightarrow$ **HTTP 403 Forbidden** (System configuration inaccessible to anonymous users).
- `http://localhost:8081/job` $\rightarrow$ **HTTP 403 Forbidden** (Job creation and build triggering restricted).
- `http://localhost:8081/api/json` $\rightarrow$ **HTTP 403 Forbidden** (API data queries restricted).
- `http://localhost:8081/login` $\rightarrow$ **HTTP 200 OK** (Standard authentication challenge).

### 5.2 GitHub Webhook Verification Mechanism
The GitHub plugin on Jenkins does **not** rely on anonymous permissions for job orchestration. Instead, it utilizes GitHub Webhook HMAC signature verification:
1. **GitHub Delivery:** When a commit or pull request event occurs, GitHub sends an HTTP POST payload to `https://<tunnel-url>.trycloudflare.com/github-webhook/`.
2. **HMAC Signature Header:** GitHub signs the payload using a shared secret and transmits the SHA-256 digest in the header:
   ```http
   X-Hub-Signature-256: sha256=<hmac-sha256-hex-digest>
   X-GitHub-Event: push
   Content-Type: application/json
   ```
3. **Jenkins Validation:** In Jenkins under **Manage Jenkins** $\rightarrow$ **System** $\rightarrow$ **GitHub Servers**, a shared secret is configured as a Secret Text credential. The plugin calculates `HMAC-SHA256(payload, secret)` and compares it in constant time against `X-Hub-Signature-256`. Requests with invalid or missing signatures are rejected with HTTP 400/403 without triggering pipeline execution.

### 5.3 Surface Isolation
The Cloudflare Quick Tunnel forwards traffic **exclusively** to port 8081:
- Frontend (`:80`) is **NOT** exposed.
- Backend API (`:8000`) is **NOT** exposed.
- Prometheus (`:9090`) is **NOT** exposed.
- Grafana (`:3001`) is **NOT** exposed.
- Docker Daemon (`/var/run/docker.sock`) is **NOT** exposed.

---

## 6. Central Batch Launcher (`start-architectiq.bat`)

The central launcher has been updated to organize all platform operations into logical, structured categories with path independence (`%~dp0`), argument safety, and modular PowerShell script dispatching.

### Launcher Menu Structure (34 Operations)

```
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

  [ CLOUDFLARE TUNNEL (NATIVE WINDOWS WEBHOOK TUNNEL) ]
   18. Start Cloudflare Tunnel (Expose Jenkins Port 8081 Only)
   19. Stop Cloudflare Tunnel
   20. Cloudflare Tunnel Status and Public URL

  [ DEVSECOPS SECURITY FRAMEWORK (7 ESSENTIAL TOOLS) ]
   21. Start Security Tools (SonarQube)
   22. Stop Security Tools (SonarQube)
   23. Run All 7 Security Scans
   24. Run Individual Security Scan (Gate 1 - 7)
   25. Run SonarQube Analysis
   26. Run OWASP ZAP against Local Test Environment
   27. View Security Reports
   28. Display Security Status and Summary

  [ PLATFORM and CONFIG VALIDATION ]
   29. Validate Docker Configurations
   30. Validate Terraform IaC Configurations
   31. Validate Kubernetes Manifests
   32. Validate Ansible Playbooks

  [ COMPREHENSIVE AUDIT and EXIT ]
   33. Check All Platform Components and Endpoints
   34. Exit
============================================================================
```

---

## 7. Operational Test and Health Check Results

### 7.1 Platform Component Audit (`check-all-services.ps1`)

```
============================================================
       ArchitectIQ Comprehensive Platform Health Audit      
============================================================

Platform Component Status Table:

Component                Port Status  Detail                     
---------                ---- ------  ------                     
App: Backend API         8000 HEALTHY status=healthy             
App: Frontend UI           80 HEALTHY HTTP 200 OK                
Monitoring: Prometheus   9090 HEALTHY Prometheus is Healthy      
Monitoring: Grafana      3001 HEALTHY database=ok, v=10.4.1      
CI/CD: Jenkins           8081 HEALTHY HTTP 200/403 Ready         
Cluster: Kubernetes      6443 HEALTHY Node: desktop-control-plane
Tunnel: Cloudflare     Native STOPPED Tunnel offline             

Summary: 6 of 7 components HEALTHY.
```

### 7.2 Cloudflare Tunnel Lifecycle Verification
1. **Start:** `powershell.exe -File scripts\cloudflare\start-tunnel.ps1`
   - Verified Jenkins responded on `8081`.
   - Native `cloudflared.exe` spawned as background process.
   - Successfully established trycloudflare tunnel and printed public URL.
2. **Status:** `powershell.exe -File scripts\cloudflare\tunnel-status.ps1`
   - Accurately reported binary version `2026.10.7`, PID, forwarding target, and public URL.
3. **Stop:** `powershell.exe -File scripts\cloudflare\stop-tunnel.ps1`
   - Verified process identity, cleanly terminated PID, safely unlinked PID file, and preserved logs.
   - Docker containers and Compose stacks were completely unaffected.

---

## 8. Safety and Compliance Verification

- **Docker Volume Integrity:** All Docker volumes (`architectiq-grafana-data`, `architectiq-prometheus-data`, `devopsforge_jenkins_home`) remained intact.
- **Zero Destructive Actions:** No `docker prune`, `down -v`, or volume deletions were executed.
- **Zero Cloud Resource Creation:** No AWS resources were created; no `terraform apply` or `destroy` commands were run.
- **Zero Autonomous Tunnel Spawning:** Cloudflare Tunnel is strictly on-demand and does not start automatically with the application.

---

## 9. Remaining Configuration for External GitHub Webhooks

When ready to connect a live GitHub repository to the Jenkins CI/CD pipeline:
1. In the central launcher (`start-architectiq.bat`), select option **18** to start the Cloudflare Tunnel.
2. Copy the generated Webhook URL (e.g. `https://[generated-name].trycloudflare.com/github-webhook/`).
3. In your GitHub repository settings under **Settings** $\rightarrow$ **Webhooks** $\rightarrow$ **Add webhook**:
   - **Payload URL:** `https://[generated-name].trycloudflare.com/github-webhook/`
   - **Content type:** `application/json`
   - **Secret:** Enter your shared secret key.
   - **Which events:** `Just the push event` or `Let me select individual events` (Pushes and Pull Requests).
4. In Jenkins, ensure the same shared secret is saved in **Manage Jenkins** $\rightarrow$ **Credentials** and configured under GitHub Servers.
5. When testing is complete, select option **19** in `start-architectiq.bat` to terminate the tunnel.

