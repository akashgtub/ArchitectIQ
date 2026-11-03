# scripts/status.ps1
# Inspects comprehensive operational status across Docker, Kubernetes, Jenkins, and Monitoring

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "         ArchitectIQ Operational Health Status      " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Ensure in project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "`n--- [1] Docker Compose Services ---" -ForegroundColor Yellow
docker compose ps

Write-Host "`n--- [2] Kubernetes Pods & Services (Namespace: architectiq) ---" -ForegroundColor Yellow
kubectl get pods,svc -n architectiq -o wide

Write-Host "`n--- [3] Jenkins Automation Controller ---" -ForegroundColor Yellow
docker ps --filter "name=jenkins" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n--- [4] Service Endpoints Check ---" -ForegroundColor Yellow
$endpoints = @(
    @{ Name = "Backend Health"; Url = "http://localhost:8000/health" },
    @{ Name = "Backend Metrics"; Url = "http://localhost:8000/metrics" },
    @{ Name = "Frontend Health"; Url = "http://localhost/healthz" },
    @{ Name = "Prometheus UI"; Url = "http://localhost:9090/-/healthy" },
    @{ Name = "Grafana UI"; Url = "http://localhost:3001/api/health" },
    @{ Name = "Jenkins UI"; Url = "http://localhost:8081/login" }
)

foreach ($ep in $endpoints) {
    try {
        $resp = Invoke-WebRequest -Uri $ep.Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-Host "[$($ep.Name)]: HTTP $($resp.StatusCode) (OK)" -ForegroundColor Green
    } catch {
        Write-Host "[$($ep.Name)]: OFFLINE or UNREACHABLE ($($_.Exception.Message))" -ForegroundColor Red
    }
}

