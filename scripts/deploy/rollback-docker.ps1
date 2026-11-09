<#
.SYNOPSIS
    Automated Docker Compose rollback script for ArchitectIQ.
.DESCRIPTION
    - Restores the last-known-good (or specified) container image tag using Docker Compose.
    - Validates post-rollback health across backend (:8000), frontend (:80), and reverse proxy.
    - Preserves existing volumes (Prometheus, Grafana, Jenkins) and network (architectiq-network).
    - Records rollback event to deployment history.
#>
[CmdletBinding()]
param(
    [string]$RollbackTag = "",
    [string]$Registry = "architectiq",
    [int]$TimeoutSec = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "      ArchitectIQ Automated Docker Compose Rollback         " -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

$historyDir = Join-Path $RepoRoot "reports\deployments"
$stateFile = Join-Path $historyDir "last-known-good.json"

if (-not $RollbackTag) {
    if (Test-Path $stateFile) {
        try {
            $lastKnown = Get-Content $stateFile -Raw | ConvertFrom-Json
            $RollbackTag = $lastKnown.ImageTag
            Write-Host "Identified last known-good tag from deployment state: '$RollbackTag'" -ForegroundColor Cyan
        } catch {
            Write-Host "[ERROR] Could not parse last-known-good.json" -ForegroundColor Red
            exit 1
        }
    } else {
        $RollbackTag = "latest"
        Write-Host "[INFO] No last-known-good.json found; defaulting rollback target to 'latest'" -ForegroundColor Cyan
    }
}

Write-Host "Rollback Target Image Tag: $RollbackTag" -ForegroundColor White
Write-Host "Image Registry:            $Registry" -ForegroundColor White
Write-Host "Health Timeout:            ${TimeoutSec}s" -ForegroundColor White
Write-Host "Compose Root:              $RepoRoot" -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor Gray

# 1. Set Environment Variables for Compose
$env:IMAGE_TAG = $RollbackTag
$env:REGISTRY_REPO = $Registry

Write-Host "`n[1/3] Redeploying target container version '$RollbackTag'..." -ForegroundColor Yellow
$upArgs = @("compose", "-f", "docker-compose.yml", "up", "-d")
$proc = Start-Process -FilePath "docker" -ArgumentList $upArgs -NoNewWindow -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    Write-Host "[ERROR] Docker Compose rollback command failed with exit code $($proc.ExitCode)." -ForegroundColor Red
    exit 1
}

# 2. Post-Rollback Health Probing
Write-Host "`n[2/3] Performing post-rollback health verification..." -ForegroundColor Yellow
$endpoints = @(
    @{ Name = "Backend Health (/health)"; Url = "http://localhost:8000/health"; Expected = 200 },
    @{ Name = "Frontend Healthz (/healthz)"; Url = "http://localhost:80/healthz"; Expected = 200 },
    @{ Name = "Frontend-to-Backend Reverse Proxy (/health)"; Url = "http://localhost:80/health"; Expected = 200 }
)

$start = [DateTime]::UtcNow
$allHealthy = $false

while (([DateTime]::UtcNow - $start).TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 3
    $failedChecks = 0

    foreach ($ep in $endpoints) {
        try {
            $resp = Invoke-WebRequest -Uri $ep.Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -ne $ep.Expected) {
                $failedChecks++
            }
        } catch {
            $failedChecks++
        }
    }

    if ($failedChecks -eq 0) {
        $allHealthy = $true
        break
    }
    Write-Host "  Waiting for rollback containers to report healthy ($([math]::Round(([DateTime]::UtcNow - $start).TotalSeconds))s elapsed)..." -ForegroundColor Gray
}

if (-not $allHealthy) {
    Write-Host "`n[CRITICAL] Rollback verification failed! Services did not stabilize within ${TimeoutSec}s." -ForegroundColor Red
    exit 1
}

# 3. Log Rollback Record
Write-Host "`n[3/3] Rollback health checks passed successfully!" -ForegroundColor Green
if (-not (Test-Path $historyDir)) {
    New-Item -ItemType Directory -Path $historyDir -Force | Out-Null
}

$rollbackRecord = [PSCustomObject]@{
    Timestamp   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    ImageTag    = $RollbackTag
    Registry    = $Registry
    Status      = "ROLLED_BACK"
    TriggeredBy = "Automated/Manual Rollback Procedure"
    CommitSha   = (git rev-parse HEAD 2>$null)
}

$historyFile = Join-Path $historyDir "deployment-history.jsonl"
($rollbackRecord | ConvertTo-Json -Compress) | Out-File -FilePath $historyFile -Encoding UTF8 -Append

# Update active last-known-good to this validated rollback tag
$rollbackRecord | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8 -Force

Write-Host "============================================================" -ForegroundColor Green
Write-Host "   Rollback to ArchitectIQ '$RollbackTag' Completed: SUCCESS " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
exit 0

