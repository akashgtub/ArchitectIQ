# ArchitectIQ — Monitoring & Observability Guide

## 1. Overview

ArchitectIQ integrates Prometheus and Grafana to provide continuous observability across service availability, health endpoints, response latencies, and container runtime states.

---

## 2. Prometheus Configuration (`infrastructure/monitoring/prometheus/`)

Prometheus operates with a 15-second evaluation interval and scrapes the following targets:

| Job Name | Target | Scrape Path | Interval | Description |
| :--- | :--- | :--- | :--- | :--- |
| `prometheus` | `localhost:9090` | `/metrics` | 15s | Prometheus self-monitoring |
| `architectiq-backend` | `backend:8000` | `/health` | 10s | Backend health status probe |
| `architectiq-frontend` | `frontend:80` | `/healthz` | 10s | Frontend Nginx health probe |

### Health Check Probing Mechanism
- Prometheus evaluates the HTTP response status of the target endpoint.
- An HTTP `200 OK` translates to `up == 1`. Any connection failure, timeout, or 5xx code translates to `up == 0`.

---

## 3. Grafana Dashboards (`infrastructure/monitoring/grafana/`)

Grafana is pre-configured using declarative provisioning files:
- **Datasource**: Automatically connects to `http://prometheus:9090` as the default Prometheus provider (`provisioning/datasources/datasource.yml`).
- **Dashboard Provisioner**: Automatically loads JSON dashboards from `/etc/grafana/dashboards` (`provisioning/dashboards/dashboards.yml`).
- **Pre-Built Dashboard**: `architectiq-overview.json` provides visual widgets for:
  1. **Backend Availability**: Real-time stat panel (Green = Healthy, Red = Down).
  2. **Frontend Availability**: Real-time stat panel.
  3. **Prometheus Health**: Scraper status stat panel.
  4. **Health Probe Latency**: Continuous timeseries chart of `scrape_duration_seconds`.
  5. **Uptime History**: 15-minute historical timeline tracking service uptime deltas.

---

## 4. Application Metrics Evolution

Currently, ArchitectIQ exposes production health via `/health` and `/healthz`.

To expose fine-grained Prometheus application metrics (such as `architectiq_simulations_total`, `architectiq_request_duration_seconds_bucket`, and error counters), the FastAPI backend can incorporate the standard `prometheus-fastapi-instrumentator` package.

Because application business logic changes require explicit authorization, this enhancement is documented as an optional next step.

