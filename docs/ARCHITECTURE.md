# ArchitectIQ — System Architecture & Engineering Specification

## 1. Executive Summary

**ArchitectIQ** is an autonomous AI-powered system engineering and optimization platform. It ingests system architecture topologies, parses them into directed NetworkX graph models, simulates discrete-event workloads under configurable read/write ratios, identifies latency and capacity bottlenecks, discovers Pareto-optimal architectures via multi-objective genetic algorithms (NSGA-II), and verifies system resilience through chaos fault-injection experiments.

The platform is designed with a **stateless, in-memory execution model** requiring zero relational or NoSQL database servers, maximizing throughput, resilience, and operational simplicity.

---

## 2. High-Level System Architecture

```
                                  [ Internet / Clients ]
                                             │
                                             ▼
                                  ┌────────────────────┐
                                  │   Nginx Frontend   │
                                  │    Port 80 (HTTP)  │
                                  └──────────┬─────────┘
                                             │ Reverse Proxy (/api, /health)
                                             ▼
                                  ┌────────────────────┐
                                  │  FastAPI Backend   │
                                  │   Port 8000 (HTTP) │
                                  └──────────┬─────────┘
                                             │
         ┌───────────────────────────────────┼───────────────────────────────────┐
         ▼                                   ▼                                   ▼
┌──────────────────┐               ┌──────────────────┐               ┌──────────────────┐
│ NetworkX Graphs  │               │ SimPy Discrete   │               │ NSGA-II Genetic  │
│ Topology Model   │               │ Event Simulator  │               │ Optimizer Engine │
└──────────────────┘               └──────────────────┘               └──────────────────┘
         │                                   │                                   │
         └───────────────────────────────────┼───────────────────────────────────┘
                                             │ Native Prometheus Instrumentation (/metrics)
                                             ▼
                                  ┌────────────────────┐
                                  │ Prometheus Scraper │
                                  │   Port 9090 (HTTP) │
                                  └──────────┬─────────┘
                                             │ PromQL Data Source
                                             ▼
                                  ┌────────────────────┐
                                  │ Grafana Dashboard  │
                                  │   Port 3001 (HTTP) │
                                  └────────────────────┘
```

---

## 3. Component Architecture

### Component 1: Application Runtime (Docker Compose)
- **Container `architectiq-frontend`**:
  - Base Image: `nginx:alpine`
  - Content: Pre-compiled React/Vite SPA bundle (`dist/index.html`, `dist/assets/*`).
  - Network: Attached to `architectiq-network`.
  - Port Mappings: Host port `80` -> Container port `80`.
  - Healthcheck: Probes `http://localhost/healthz` every 10s.
  - Reverse Proxy: Proxies API calls directly to `http://backend:8000`.

- **Container `architectiq-backend`**:
  - Base Image: `python:3.11-slim`
  - Framework: FastAPI with Uvicorn ASGI server.
  - Network: Attached to `architectiq-network` (service DNS: `backend`).
  - Port Mappings: Host port `8000` -> Container port `8000`.
  - Healthcheck: Probes `http://localhost:8000/health` every 10s.
  - In-Memory State: All simulation runs, pareto frontiers, and investigation sessions are held in high-speed Python memory structures.

### Component 2: Observability & Monitoring Stack
- **Container `architectiq-prometheus`**:
  - Base Image: `prom/prometheus:v2.45.0`
  - Port Mappings: Host port `9090` -> Container port `9090`.
  - Scrape Config: 5s scrape interval targeting `backend:8000/metrics`, `frontend:80/healthz`, and `localhost:9090`.
  - Volume: Named persistent volume `architectiq-prometheus-data`.

- **Container `architectiq-grafana`**:
  - Base Image: `grafana/grafana:10.0.0`
  - Port Mappings: Host port `3001` -> Container port `3000`.
  - Provisioning: Automated datasources (`datasource.yml`) and dashboards (`architectiq-overview.json`).
  - Volume: Named persistent volume `architectiq-grafana-data`.

### Component 3: CI/CD Automation & DevSecOps Platform
- **Container `devopsforge-jenkins`**:
  - Port Mappings: Host port `8081` -> Container port `8080`, port `50000` for JNLP agents.
  - Docker Socket: Mounted `/var/run/docker.sock` allowing native container building and tagging.
  - Persistent Volume: `devopsforge_jenkins_home`.

- **Windows Self-Hosted GitHub Actions Runner**:
  - Service: `ARCHITECTIQ-WIN-RUNNER` running in `C:\actions-runner`.
  - Triggers: Pushes to `main` branch or manual `workflow_dispatch`.
  - Bridge: Executes `scripts/ci/trigger-jenkins.ps1`, captures Jenkins build results, downloads DevSecOps summaries, and triggers zero-downtime automated deployment via `scripts/deploy/deploy-docker.ps1`.

---

## 4. Network Topology & Port Allocation

| Port | Service | Container Name | Ingress Access | Health Check URL |
| :---: | :--- | :--- | :--- | :--- |
| **80** | Nginx Web Frontend | `architectiq-frontend` | Public / Host | `http://localhost:80/healthz` |
| **8000** | FastAPI Application API | `architectiq-backend` | Internal / Host | `http://localhost:8000/health` |
| **3001** | Grafana Dashboards | `architectiq-grafana` | Host / Admin | `http://localhost:3001/api/health` |
| **9090** | Prometheus Server | `architectiq-prometheus` | Host / Scraper | `http://localhost:9090/-/healthy` |
| **8081** | Jenkins CI/CD Controller | `devopsforge-jenkins` | Host / CI Agent | `http://localhost:8081/login` |

All services share the bridge network `architectiq-network` (`172.28.0.0/16`), allowing isolated container-to-container communication by container service name without host-level DNS dependencies.

