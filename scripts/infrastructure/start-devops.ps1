<#
.SYNOPSIS
    Starts all DevOps Infrastructure components (Monitoring Stack + Jenkins Controller).
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevOps Infrastructure Launcher           " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Start Monitoring Stack
Write-Host "`n[1/2] Starting Monitoring Stack (Prometheus + Grafana)..." -ForegroundColor Yellow
& (Join-Path $RepoRoot "scripts\monitoring\start-monitoring.ps1")

# 2. Start Jenkins Controller
Write-Host "`n[2/2] Starting Jenkins Controller..." -ForegroundColor Yellow
& (Join-Path $RepoRoot "scripts\jenkins\start-jenkins.ps1")

Write-Host "`nDevOps Infrastructure is active." -ForegroundColor Green

