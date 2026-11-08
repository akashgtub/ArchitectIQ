<#
.SYNOPSIS
    Starts independent security services (SonarQube container).
    Implements memory check (requires ~2.5GB RAM) and safe, idempotent container lifecycle.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevSecOps Security Tools Launcher        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. System Memory Check
$os = Get-CimInstance Win32_OperatingSystem
$freeMB = [math]::Round($os.FreePhysicalMemory / 1024, 0)
$requiredMB = 2560

Write-Host "System Memory Check: Free Physical RAM = ${freeMB} MB (Required: ${requiredMB} MB)" -ForegroundColor Yellow
if ($freeMB -lt $requiredMB) {
    Write-Host "[SKIPPED] Insufficient memory for SonarQube (Available: ${freeMB} MB, Required: ${requiredMB} MB)." -ForegroundColor Yellow
    Write-Host "SonarQube startup skipped safely to protect Jenkins and application stability." -ForegroundColor Yellow
    exit 0
}

# 2. Idempotent Container Startup
$containerName = "architectiq-sonarqube"
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
    Write-Host "  [CREATING] Container '$containerName' not found. Creating via Compose..." -ForegroundColor Yellow
    docker compose -f infrastructure/security/docker-compose.security.yml up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to start security tools compose stack." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# 3. Wait for Readiness
Write-Host "`nVerifying SonarQube service readiness..." -ForegroundColor Yellow
$sonarReady = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:9000/api/system/status" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($resp.status -eq "UP") {
            $sonarReady = $true
            break
        }
    } catch {}
}

Write-Host "`nSonarQube Security Service:" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host ("SonarQube Web UI: http://localhost:9000     [{0}]" -f ($(if ($sonarReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($sonarReady) { "Green" } else { "Yellow" })
Write-Host "Credentials:      admin / admin"
Write-Host "Data Volumes:     architectiq-sonarqube-data, extensions, logs (Preserved)"
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
