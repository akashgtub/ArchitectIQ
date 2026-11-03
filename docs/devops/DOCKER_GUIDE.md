# ArchitectIQ — Docker Containerization Guide

## 1. Overview

ArchitectIQ utilizes containerization to ensure identical behavior across local development, CI testing, and production Kubernetes clusters. Both the Python FastAPI backend and the Vite Single-Page Application frontend are containerized using production best practices.

---

## 2. Backend Container (`backend/Dockerfile`)

### Key Characteristics
- **Base Image**: `python:3.11-slim` (matches the 3.11.9 runtime specified in `render.yaml`).
- **Security**: Runs under an unprivileged user (`appuser`, UID/GID `10001:10001`). Root execution is explicitly prohibited.
- **Port**: Exposes port `8000`.
- **Healthcheck**: Uses `curl` to query `http://localhost:8000/health` every 30 seconds.
- **Entrypoint**: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.

### Example Build & Run Commands (Reference Only)
```bash
docker build -t architectiq/backend:v1.0.0 -f backend/Dockerfile .

docker run -d \
  --name architectiq-backend \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e AI_PROVIDER=auto \
  -e ALLOW_AI_FALLBACK=true \
  architectiq/backend:v1.0.0
```

---

## 3. Frontend Container (`frontend/Dockerfile`)

### Key Characteristics
- **Multi-Stage Architecture**:
  - **Stage 1 (Builder)**: `node:20-alpine` runs `npm ci` and `npm run build` to compile the Vite single-page application into `dist/`.
  - **Stage 2 (Runtime)**: `nginx:1.25-alpine` serves the static bundle and acts as a reverse proxy for `/api/` and `/health` requests to the backend.
- **Security**: Hardened Nginx configuration with custom HTTP security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`).
- **Port**: Exposes port `80`.
- **Healthcheck**: Uses `wget` to poll `http://localhost/healthz`.

### Example Build & Run Commands (Reference Only)
```bash
docker build -t architectiq/frontend:v1.0.0 -f frontend/Dockerfile .

docker run -d \
  --name architectiq-frontend \
  -p 80:80 \
  architectiq/frontend:v1.0.0
```

---

## 4. Local Multi-Container Development (`docker-compose.yml`)

The root `docker-compose.yml` provides a unified local environment connecting all components over the custom bridge network `architectiq-net`:

1. **`backend`**: FastAPI application service (port 8000).
2. **`frontend`**: Nginx web server and reverse proxy (port 80).
3. **`prometheus`**: Time-series metrics server (port 9090).
4. **`grafana`**: Visualization dashboards (port 3001).

### Compose Lifecycle Commands (Reference Only)
```bash
docker-compose up -d --build

docker-compose logs -f

docker-compose ps

docker-compose down
```

