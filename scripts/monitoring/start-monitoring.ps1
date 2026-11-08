<#
.SYNOPSIS
    Starts the Monitoring & Observability Stack (Prometheus + Grafana).
    Implements safe, idempotent startup: reuses running containers,
    starts stopped containers, or creates via Compose.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Monitoring Stack Launcher                " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Helper: Safe Container Startup
function Start-IdempotentContainer {
    param (
        [string]$Name,
        [string]$Service
    )
    $inspect = docker inspect $Name 2>$null
    if ($LASTEXITCODE -eq 0 -and $inspect) {
        $state = ($inspect | ConvertFrom-Json).State
        if ($state.Running) {
            Write-Host "  [REUSED] Container '$Name' is already running." -ForegroundColor Green
            return
        } else {
            Write-Host "  [STARTING] Container '$Name' exists but is stopped. Starting..." -ForegroundColor Yellow
            docker start $Name | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [REUSED] Container '$Name' started successfully." -ForegroundColor Green
                return
            }
        }
    }
    Write-Host "  [CREATING] Container '$Name' not found. Creating via Compose..." -ForegroundColor Yellow
    docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml up -d $Service
}

Write-Host "`n[1/2] Ensuring Prometheus and Grafana containers are running..." -ForegroundColor Yellow
Start-IdempotentContainer -Name "architectiq-prometheus" -Service "prometheus"
Start-IdempotentContainer -Name "architectiq-grafana" -Service "grafana"

# 2. Verify Health
Write-Host "`n[2/2] Verifying Prometheus & Grafana readiness..." -ForegroundColor Yellow
$promReady = $false
$grafanaReady = $false

for ($i = 1; $i -le 10; $i++) {
    Start-Sleep -Seconds 2
    if (-not $promReady) {
        try {
            $web = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($web.StatusCode -eq 200) { $promReady = $true }
        } catch {}
    }
    if (-not $grafanaReady) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:3001/api/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.database -eq "ok") { $grafanaReady = $true }
        } catch {}
    }
    if ($promReady -and $grafanaReady) { break }
}

Write-Host "`nMonitoring Services Status:" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host ("Prometheus:      http://localhost:9090     [{0}]" -f ($(if ($promReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($promReady) { "Green" } else { "Yellow" })
Write-Host ("Grafana:         http://localhost:3001     [{0}] (admin / admin)" -f ($(if ($grafanaReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($grafanaReady) { "Green" } else { "Yellow" })
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
