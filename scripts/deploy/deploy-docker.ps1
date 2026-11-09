<#
.SYNOPSIS
    Automated minimal-downtime Docker Compose deployment script for ArchitectIQ.
.DESCRIPTION
    - Deploys new backend and frontend container versions using Docker Compose.
    - Note on Downtime: Single-instance container recreation incurs a minimal ~1-3s cutover interruption.
    - Validates post-deployment health across backend (:8000), frontend (:80), and reverse proxy.
    - Preserves existing volumes (Prometheus, Grafana, Jenkins) and network (architectiq-network).
    - Automatically rolls back if health checks fail within the timeout period.
    - Records immutable deployment history with commit SHA and image tag.
#>
[CmdletBinding()]
param(
    [string]$ImageTag = "latest",
    [string]$Registry = "architectiq",
    [int]$TimeoutSec = 60,
    [switch]$ForceRecreate
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   ArchitectIQ Production-Style Docker Compose Deployment    " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Target Image Tag:  $ImageTag" -ForegroundColor White
Write-Host "Image Registry:    $Registry" -ForegroundColor White
Write-Host "Health Timeout:    ${TimeoutSec}s" -ForegroundColor White
Write-Host "Compose Root:      $RepoRoot" -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor Gray

# 1. Capture Previous Known-Good State for Rollback
$stateFile = Join-Path $RepoRoot "reports\deployments\last-known-good.json"
$historyDir = Join-Path $RepoRoot "reports\deployments"
if (-not (Test-Path $historyDir)) {
    New-Item -ItemType Directory -Path $historyDir -Force | Out-Null
}

$previousState = $null
if (Test-Path $stateFile) {
    try {
        $previousState = Get-Content $stateFile -Raw | ConvertFrom-Json
        Write-Host "Previous deployment state loaded: Tag '$($previousState.ImageTag)' (Timestamp: $($previousState.Timestamp))" -ForegroundColor Gray
    } catch {}
}

# 2. Set Environment Variables for Deployment
$env:IMAGE_TAG = $ImageTag
$env:REGISTRY_REPO = $Registry

Write-Host "`n[1/3] Deploying services via Docker Compose..." -ForegroundColor Yellow
$upArgs = @("compose", "-f", "docker-compose.yml", "up", "-d")
if ($ForceRecreate) {
    $upArgs += "--force-recreate"
}

$proc = Start-Process -FilePath "docker" -ArgumentList $upArgs -NoNewWindow -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    Write-Host "[ERROR] Docker Compose deployment command failed with exit code $($proc.ExitCode)." -ForegroundColor Red
    exit 1
}

# 3. Post-Deployment Automated Health Probing
Write-Host "`n[2/3] Performing post-deployment health verification..." -ForegroundColor Yellow
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
    Write-Host "  Waiting for containers to report healthy ($([math]::Round(([DateTime]::UtcNow - $start).TotalSeconds))s elapsed)..." -ForegroundColor Gray
}

# 4. Handle Health Failure -> Automatic Rollback
if (-not $allHealthy) {
    Write-Host "`n[ERROR] Health verification failed! Application containers did not respond within ${TimeoutSec}s." -ForegroundColor Red
    if ($previousState -and $previousState.ImageTag -and $previousState.ImageTag -ne $ImageTag) {
        Write-Host "Initiating AUTOMATIC ROLLBACK to known-good image tag '$($previousState.ImageTag)'..." -ForegroundColor Yellow
        & (Join-Path $PSScriptRoot "rollback-docker.ps1") -RollbackTag $previousState.ImageTag
        exit 1
    } else {
        Write-Host "[WARNING] No previous known-good deployment recorded. Manual intervention required." -ForegroundColor Red
        exit 1
    }
}

# 5. Success -> Record Deployment State & History
Write-Host "`n[3/3] All health checks passed successfully!" -ForegroundColor Green
$deployRecord = [PSCustomObject]@{
    Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    ImageTag  = $ImageTag
    Registry  = $Registry
    Status    = "SUCCESS"
    CommitSha = (git rev-parse HEAD 2>$null)
}

$deployRecord | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8 -Force
$historyFile = Join-Path $historyDir "deployment-history.jsonl"
($deployRecord | ConvertTo-Json -Compress) | Out-File -FilePath $historyFile -Encoding UTF8 -Append

Write-Host "============================================================" -ForegroundColor Green
Write-Host "   Deployment of ArchitectIQ '$ImageTag' Completed: SUCCESS  " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
exit 0

