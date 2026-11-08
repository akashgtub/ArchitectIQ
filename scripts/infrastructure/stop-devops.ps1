<#
.SYNOPSIS
    Stops all DevOps Infrastructure components (Monitoring Stack + Jenkins Controller).
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevOps Infrastructure Stopper            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Stop Jenkins Controller
Write-Host "`n[1/2] Stopping Jenkins Controller..." -ForegroundColor Yellow
& (Join-Path $RepoRoot "scripts\jenkins\stop-jenkins.ps1")

# 2. Stop Monitoring Stack
Write-Host "`n[2/2] Stopping Monitoring Stack..." -ForegroundColor Yellow
& (Join-Path $RepoRoot "scripts\monitoring\stop-monitoring.ps1")

Write-Host "`nDevOps Infrastructure stopped." -ForegroundColor Green

