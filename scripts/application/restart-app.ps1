<#
.SYNOPSIS
    Restarts the ArchitectIQ Application containers and verifies health.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Application Restarter                    " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Restarting application containers..." -ForegroundColor Yellow
docker compose restart

& (Join-Path $PSScriptRoot "app-status.ps1")

