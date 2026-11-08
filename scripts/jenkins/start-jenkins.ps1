<#
.SYNOPSIS
    Starts the Jenkins CI/CD controller container.
    Implements safe, idempotent startup: reuses running container,
    starts stopped container, or creates via Compose.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Jenkins CI/CD Controller Launcher         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Start Jenkins via Idempotent Lifecycle
Write-Host "`n[1/2] Ensuring Jenkins controller container is running..." -ForegroundColor Yellow
$containerName = "devopsforge-jenkins"
$inspect = docker inspect $containerName 2>$null
if ($LASTEXITCODE -eq 0 -and $inspect) {
    $state = ($inspect | ConvertFrom-Json).State
    if ($state.Running) {
        Write-Host "  [REUSED] Container '$containerName' is already running." -ForegroundColor Green
    } else {
        Write-Host "  [STARTING] Container '$containerName' exists but is stopped. Starting..." -ForegroundColor Yellow
        docker start $containerName | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [REUSED] Container '$containerName' started successfully." -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to start stopped container '$containerName'." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "  [CREATING] Container '$containerName' not found. Creating via Docker Compose..." -ForegroundColor Yellow
    docker compose -f infrastructure/jenkins/docker-compose.jenkins.yml up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to start Jenkins compose stack." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# 2. Verify Health / Responsiveness
Write-Host "`n[2/2] Verifying Jenkins controller readiness..." -ForegroundColor Yellow
$jenkinsReady = $false

for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $web = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($web.StatusCode -eq 200 -or $web.StatusCode -eq 403) {
            $jenkinsReady = $true
            break
        }
    } catch {
        if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 403 -or $_.Exception.Response.StatusCode.value__ -eq 200)) {
            $jenkinsReady = $true
            break
        }
    }
}

Write-Host "`nJenkins CI/CD Status:" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host ("Jenkins UI:      http://localhost:8081     [{0}]" -f ($(if ($jenkinsReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($jenkinsReady) { "Green" } else { "Yellow" })
Write-Host "Agent Port:      50000" -ForegroundColor Cyan
Write-Host "Security:        Localhost Only (Private)" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
