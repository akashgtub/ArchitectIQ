<#
.SYNOPSIS
    Starts the ArchitectIQ Application (Frontend + Backend).
    Implements safe, idempotent startup: reuses running containers,
    starts stopped containers, or creates missing containers via Compose.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Application Launcher (Frontend + Backend)  " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify Docker Engine
try {
    docker info >$null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker engine is not running."
    }
} catch {
    Write-Host "[ERROR] Docker engine is not accessible. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# 2. Helper: Safe Container Startup
function Start-IdempotentContainer {
    param (
        [string]$Name,
        [string]$Service
    )
    $inspect = docker inspect $Name 2>$null
    if ($LASTEXITCODE -eq 0 -and $inspect) {
        $state = ($inspect | ConvertFrom-Json).State
        if ($state.Running) {
            Write-Host "  [REUSED] Container '$Name' is already running." -ForegroundColor Green
            return
        } else {
            Write-Host "  [STARTING] Container '$Name' exists but is stopped. Starting..." -ForegroundColor Yellow
            docker start $Name | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [REUSED] Container '$Name' started successfully." -ForegroundColor Green
                return
            }
        }
    }
    Write-Host "  [CREATING] Container '$Name' not found. Creating via Docker Compose..." -ForegroundColor Yellow
    docker compose up -d $Service
}

Write-Host "`n[1/3] Starting ArchitectIQ application containers..." -ForegroundColor Yellow
Start-IdempotentContainer -Name "architectiq-backend" -Service "backend"
Start-IdempotentContainer -Name "architectiq-frontend" -Service "frontend"

# 3. Wait for Healthy Status
Write-Host "`n[2/3] Verifying backend and frontend health..." -ForegroundColor Yellow
$backendReady = $false
$frontendReady = $false

for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    if (-not $backendReady) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.status -eq "ok" -or $resp.status -eq "healthy") {
                $backendReady = $true
            }
        } catch {}
    }
    if (-not $frontendReady) {
        try {
            $web = Invoke-WebRequest -Uri "http://localhost" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($web.StatusCode -eq 200) {
                $frontendReady = $true
            }
        } catch {}
    }
    if ($backendReady -and $frontendReady) {
        break
    }
    Write-Host "  Waiting for services to become healthy ($($i * 2)s)..." -ForegroundColor Gray
}

# 4. Report Final Status
Write-Host "`n[3/3] ArchitectIQ Application Status:" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host ("Frontend UI:     http://localhost          [{0}]" -f ($(if ($frontendReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($frontendReady) { "Green" } else { "Yellow" })
Write-Host ("Backend API:     http://localhost:8000     [{0}]" -f ($(if ($backendReady) { "READY" } else { "STARTING" }))) -ForegroundColor $(if ($backendReady) { "Green" } else { "Yellow" })
Write-Host "API Swagger:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Health Probe:    http://localhost:8000/health" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Gray
Write-Host "Note: Database is In-Memory. Monitoring and Jenkins are decoupled." -ForegroundColor DarkCyan
