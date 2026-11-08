<#
.SYNOPSIS
    Validates Docker Compose specifications and Dockerfiles.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Docker Configuration Validation          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$success = $true

# 1. Root Compose
Write-Host "`n[1/3] Validating Root docker-compose.yml (App: Backend + Frontend)..." -ForegroundColor Yellow
$out1 = docker compose -f docker-compose.yml config 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  PASS: Root docker-compose.yml syntax is valid." -ForegroundColor Green
} else {
    Write-Host "  FAIL: Root docker-compose.yml has errors:`n$out1" -ForegroundColor Red
    $success = $false
}

# 2. Monitoring Compose
Write-Host "`n[2/3] Validating Monitoring docker-compose.monitoring.yml..." -ForegroundColor Yellow
$out2 = docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml config 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  PASS: Monitoring compose syntax is valid." -ForegroundColor Green
} else {
    Write-Host "  FAIL: Monitoring compose has errors:`n$out2" -ForegroundColor Red
    $success = $false
}

# 3. Jenkins Compose
Write-Host "`n[3/3] Validating Jenkins docker-compose.jenkins.yml..." -ForegroundColor Yellow
$out3 = docker compose -f infrastructure/jenkins/docker-compose.jenkins.yml config 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  PASS: Jenkins compose syntax is valid." -ForegroundColor Green
} else {
    Write-Host "  FAIL: Jenkins compose has errors:`n$out3" -ForegroundColor Red
    $success = $false
}

Write-Host "============================================================" -ForegroundColor Cyan
if ($success) {
    Write-Host "Docker Validation: ALL COMPOSE CONFIGS VALID (PASS)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Docker Validation: CONFIGURATION ERRORS DETECTED (FAIL)" -ForegroundColor Red
    exit 1
}

