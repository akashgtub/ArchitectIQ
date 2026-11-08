<#
.SYNOPSIS
    Stops the ArchitectIQ Application containers (Frontend + Backend).
    Does not delete containers or volumes.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Application Stopper                      " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Stopping application containers (frontend and backend)..." -ForegroundColor Yellow
docker compose stop

Write-Host "Application containers have stopped." -ForegroundColor Green

