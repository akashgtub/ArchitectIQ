<#
.SYNOPSIS
    Stops the Monitoring & Observability Stack (Prometheus + Grafana).
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Monitoring Stack Stopper                 " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Stopping Prometheus and Grafana containers..." -ForegroundColor Yellow
docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml stop

Write-Host "Monitoring stack containers stopped." -ForegroundColor Green

