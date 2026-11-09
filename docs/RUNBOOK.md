# ArchitectIQ — SRE & Operations Runbook

## 1. Quick Service Health Verification

To verify the operational status of all platform services in a single command:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy-docker.ps1 -ImageTag latest
```
Or query endpoints directly:
- **Frontend SPA**: `curl -I http://localhost:80/healthz` (Expected: HTTP 200)
- **Backend API**: `curl -s http://localhost:8000/health` (Expected: `{"status":"healthy"}`)
- **Reverse Proxy**: `curl -s http://localhost:80/health` (Expected: `{"status":"healthy"}`)
- **Prometheus**: `curl -s http://localhost:9090/-/healthy` (Expected: `Prometheus Server is Healthy.`)
- **Grafana**: `curl -s http://localhost:3001/api/health` (Expected: `{"database":"ok"}`)
- **Jenkins**: `curl -I http://localhost:8081/login` (Expected: HTTP 200)

---

## 2. Automated Deployment Procedure

To deploy a newly built image or update running containers:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy-docker.ps1 -ImageTag <IMAGE_TAG>
```
What this does:
1. Backs up the current active image tag in `reports/deployments/last-known-good.json`.
2. Updates running containers using `docker compose -f docker-compose.yml up -d`.
3. Sequentially probes `:8000/health`, `:80/healthz`, and `:80/health` every 3 seconds up to 60 seconds.
4. If all checks pass, appends the success entry to `reports/deployments/deployment-history.jsonl`.
5. If any check fails, automatically invokes `rollback-docker.ps1` to restore the previous stable image.

---

## 3. Rollback Procedure

To roll back immediately to the last known-good configuration:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\rollback-docker.ps1
```
To roll back to a specific historical tag:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy\rollback-docker.ps1 -RollbackTag <TAG_NAME>
```

---

## 4. Viewing Logs & Debugging

- **Backend Application Logs**:
  ```powershell
  docker logs -f --tail 100 architectiq-backend
  ```
- **Frontend Nginx Ingress Logs**:
  ```powershell
  docker logs -f --tail 100 architectiq-frontend
  ```
- **Prometheus Scrape Status**:
  Visit `http://localhost:9090/targets` or run:
  ```powershell
  curl -s http://localhost:9090/api/v1/targets | jq .data.activeTargets
  ```
- **Jenkins CI/CD Logs**:
  ```powershell
  docker logs -f --tail 100 devopsforge-jenkins
  ```

---

## 5. Security Gate Scans (DevSecOps)

To run the seven security gates manually:
```powershell
# Run in ADVISORY mode (non-blocking)
python security\framework\seven_gates_runner.py --mode ADVISORY

# Run in STRICT mode (halts on policy failure)
python security\framework\seven_gates_runner.py --mode STRICT

# View aggregated executive summary
python security\framework\seven_gates_runner.py --summary
```
Generated reports are stored in `reports/security/gate-01` through `gate-07.json` and `security-summary.md`.

---

## 6. Restarting Services Safely

To restart application containers without volume data loss:
```powershell
docker compose -f docker-compose.yml restart
```
To restart monitoring containers:
```powershell
docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml restart
```
> [!CAUTION]
> Never run `docker system prune` or `docker volume prune`. Volume data for Grafana (`architectiq-grafana-data`), Prometheus (`architectiq-prometheus-data`), and Jenkins (`devopsforge_jenkins_home`) must be permanently preserved.

