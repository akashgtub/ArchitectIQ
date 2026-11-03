# scripts/stop-architectiq.ps1
# Gracefully stops the ArchitectIQ Docker Compose stack preserving volumes

$ErrorActionPreference = "Stop"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "        Stopping ArchitectIQ Application Stack      " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Ensure in project root
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Stopping Docker Compose containers (preserving data volumes)..." -ForegroundColor Yellow
docker compose stop

Write-Host "`nArchitectIQ containers stopped cleanly." -ForegroundColor Green
docker compose ps

