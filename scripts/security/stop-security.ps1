<#
.SYNOPSIS
    Stops independent security services (SonarQube container).
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevSecOps Security Tools Stopper         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Stopping SonarQube container..." -ForegroundColor Yellow
docker compose -f infrastructure/security/docker-compose.security.yml stop

Write-Host "Security tools containers stopped." -ForegroundColor Green

