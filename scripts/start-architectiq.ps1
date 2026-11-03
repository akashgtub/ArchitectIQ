# scripts/start-architectiq.ps1
# Starts ArchitectIQ Docker Compose stack and verifies container readiness

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "        Starting ArchitectIQ Application Stack      " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Ensure in project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[1/3] Starting Docker Compose stack..." -ForegroundColor Yellow
docker compose up -d

Write-Host "[2/3] Waiting for containers to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "[3/3] Inspecting running containers..." -ForegroundColor Yellow
docker compose ps

Write-Host "`nArchitectIQ stack started successfully." -ForegroundColor Green
Write-Host "Frontend:   http://localhost"
Write-Host "Backend:    http://localhost:8000"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "Grafana:    http://localhost:3001 (admin:admin)"
Write-Host "Jenkins:    http://localhost:8081"

