<#
.SYNOPSIS
    Automated minimal-downtime Docker Compose deployment script for ArchitectIQ.
.DESCRIPTION
    - Robust, environment-aware Docker executable and Docker Compose resolution.
    - Pre-deployment Docker Engine connectivity verification.
    - Strict release image tag validation (ensures backend and frontend release tags match and exist).
    - Deploys new backend and frontend container versions using Docker Compose.
    - Preserves existing volumes (Prometheus, Grafana, Jenkins) and network (architectiq-network).
    - Validates post-deployment health across backend (:8000), frontend (:80), and reverse proxy (:80/health).
    - Automatically rolls back if health checks fail within the timeout period.
    - Records immutable deployment history with commit SHA and image tag.
#>
[CmdletBinding()]
param(
    [string]$ImageTag = "",
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
Write-Host "Execution User:    $([System.Environment]::UserDomainName)\$([System.Environment]::UserName)" -ForegroundColor Gray
Write-Host "Compose Root:      $RepoRoot" -ForegroundColor Gray
Write-Host "Health Timeout:    ${TimeoutSec}s" -ForegroundColor White
Write-Host "Image Registry:    $Registry" -ForegroundColor White

# ---------------------------------------------------------------------------
# 1. Environment-Aware Docker Executable Resolution
# ---------------------------------------------------------------------------
Write-Host "`n[1/5] Resolving Docker executable and CLI environment..." -ForegroundColor Yellow

function Find-DockerExecutable {
    # 1. Check current PATH
    $cmd = Get-Command "docker.exe" -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $cmd = Get-Command "docker" -ErrorAction SilentlyContinue
    }
    if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
        return $cmd.Source
    }

    # 2. Check standard system-wide installation locations
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"),
        (Join-Path $env:ProgramFiles "Docker\resources\bin\docker.exe")
    )
    if ($env:ProgramW6432) {
        $candidates += (Join-Path $env:ProgramW6432 "Docker\Docker\resources\bin\docker.exe")
    }

    # 3. Check current user AppData
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe")
    }
    if ($env:USERPROFILE) {
        $candidates += (Join-Path $env:USERPROFILE "AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe")
    }

    # 4. Check all local user profiles (for services running under Service Accounts)
    $userDirs = Get-ChildItem -Path "C:\Users" -Directory -ErrorAction SilentlyContinue
    if ($userDirs) {
        foreach ($u in $userDirs) {
            $candidates += (Join-Path $u.FullName "AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe")
        }
    }

    foreach ($path in $candidates) {
        if ($path -and (Test-Path $path -ErrorAction SilentlyContinue)) {
            return $path
        }
    }

    return $null
}

$dockerExe = Find-DockerExecutable

if (-not $dockerExe) {
    Write-Host "[FATAL] Docker CLI executable (docker.exe) could not be resolved." -ForegroundColor Red
    Write-Host "Checked PATH and standard locations under Program Files and AppData." -ForegroundColor Yellow
    Write-Host "Ensure Docker Desktop is installed and accessible to the executing user account." -ForegroundColor Yellow
    exit 1
}

Write-Host "Resolved Docker CLI: $dockerExe" -ForegroundColor Green

# Ensure docker directory is in PATH for child CLI plugins (e.g. docker-compose)
$dockerDir = Split-Path $dockerExe -Parent
if ($env:PATH -notlike "*$dockerDir*") {
    $env:PATH = "$dockerDir;" + $env:PATH
}

# Helper function to invoke Docker safely without PowerShell NativeCommandError on stderr warnings
function Invoke-NativeDocker {
    param([string[]]$Arguments)
    $origEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = & $dockerExe @Arguments 2>&1
        $code = $LASTEXITCODE
        return [PSCustomObject]@{
            Output   = $lines
            ExitCode = $code
        }
    } finally {
        $ErrorActionPreference = $origEap
    }
}

# ---------------------------------------------------------------------------
# 2. Verify Docker Engine Connectivity and Compose Plugin
# ---------------------------------------------------------------------------
Write-Host "`n[2/5] Verifying Docker Engine connectivity..." -ForegroundColor Yellow

# If DOCKER_HOST is not set and default named pipe fails, check desktop-linux pipe
$infoRes = Invoke-NativeDocker -Arguments @("info")
if ($infoRes.ExitCode -ne 0) {
    Write-Host "Default Docker Engine connection failed. Probing Docker Desktop Linux pipe..." -ForegroundColor Yellow
    if (Test-Path "\\.\pipe\dockerDesktopLinuxEngine" -ErrorAction SilentlyContinue) {
        $env:DOCKER_HOST = "npipe:////./pipe/dockerDesktopLinuxEngine"
        Write-Host "Configured DOCKER_HOST to npipe:////./pipe/dockerDesktopLinuxEngine" -ForegroundColor Cyan
        $infoRes = Invoke-NativeDocker -Arguments @("info")
    }
}

if ($infoRes.ExitCode -ne 0) {
    Write-Host "[FATAL] Unable to connect to Docker Engine." -ForegroundColor Red
    Write-Host "Docker CLI returned exit code $($infoRes.ExitCode):" -ForegroundColor Red
    $infoRes.Output | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "`nActionable Guidance:" -ForegroundColor Yellow
    Write-Host "1. Verify Docker Desktop is running." -ForegroundColor Yellow
    Write-Host "2. If executing as a Windows service account (e.g. NETWORK SERVICE), the service account lacks access to Docker Desktop's named pipe." -ForegroundColor Yellow
    Write-Host "   Configure the service to run as the local user account (or interactively via run.cmd)." -ForegroundColor Yellow
    exit 1
}

Write-Host "Docker Engine is connected and operational." -ForegroundColor Green

# Check Docker Compose
$composeRes = Invoke-NativeDocker -Arguments @("compose", "version")
if ($composeRes.ExitCode -ne 0) {
    Write-Host "[FATAL] Docker Compose plugin is not available." -ForegroundColor Red
    $composeRes.Output | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}
Write-Host "Docker Compose plugin verified: $(($composeRes.Output | Select-Object -First 1))" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Resolve and Verify Immutable Image Tag
# ---------------------------------------------------------------------------
Write-Host "`n[3/5] Resolving and validating release image tag..." -ForegroundColor Yellow

$stateFile = Join-Path $RepoRoot "reports\deployments\last-known-good.json"
$historyDir = Join-Path $RepoRoot "reports\deployments"
$manifestFile = Join-Path $RepoRoot "reports\deployments\build-manifest.json"

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

# Resolve target image tag if not explicitly supplied or set to "latest"
if (-not $ImageTag -or $ImageTag -eq "latest") {
    if (Test-Path $manifestFile) {
        try {
            $manifest = Get-Content $manifestFile -Raw | ConvertFrom-Json
            if ($manifest.release_tag) {
                $ImageTag = $manifest.release_tag
                Write-Host "Resolved immutable release tag from build manifest: '$ImageTag'" -ForegroundColor Cyan
            }
        } catch {}
    }
    
    if ((-not $ImageTag -or $ImageTag -eq "latest") -and $previousState -and $previousState.ImageTag -and $previousState.ImageTag -ne "latest") {
        $ImageTag = $previousState.ImageTag
        Write-Host "Resolved release tag from last-known-good state: '$ImageTag'" -ForegroundColor Cyan
    }
}

if (-not $ImageTag) {
    $ImageTag = "latest"
}

Write-Host "Target Image Tag:  $ImageTag" -ForegroundColor White

# Verify that the expected images actually exist in the local Docker Engine before attempting Compose
$backendImage = "${Registry}/backend:${ImageTag}"
$frontendImage = "${Registry}/frontend:${ImageTag}"

Write-Host "Inspecting required images in Docker Engine..." -ForegroundColor Yellow
$backendInspect = Invoke-NativeDocker -Arguments @("image", "inspect", $backendImage)
if ($backendInspect.ExitCode -ne 0) {
    Write-Host "[FATAL] Required backend image '$backendImage' not found in Docker Engine." -ForegroundColor Red
    Write-Host "The deployment pipeline requires verified pre-built images. Run the build/pipeline stage first." -ForegroundColor Yellow
    exit 1
}

$frontendInspect = Invoke-NativeDocker -Arguments @("image", "inspect", $frontendImage)
if ($frontendInspect.ExitCode -ne 0) {
    Write-Host "[FATAL] Required frontend image '$frontendImage' not found in Docker Engine." -ForegroundColor Red
    Write-Host "The deployment pipeline requires verified pre-built images. Run the build/pipeline stage first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Verified backend release image:  $backendImage" -ForegroundColor Green
Write-Host "Verified frontend release image: $frontendImage" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Deploy Services via Docker Compose
# ---------------------------------------------------------------------------
Write-Host "`n[4/5] Deploying services via Docker Compose..." -ForegroundColor Yellow

$env:IMAGE_TAG = $ImageTag
$env:REGISTRY_REPO = $Registry

$upArgs = @("compose", "-f", "docker-compose.yml", "up", "-d")
if ($ForceRecreate) {
    $upArgs += "--force-recreate"
}

Write-Host "Executing: $dockerExe $($upArgs -join ' ')" -ForegroundColor Gray
$composeDeploy = Invoke-NativeDocker -Arguments $upArgs
$composeDeploy.Output | ForEach-Object { Write-Host "  $_" -ForegroundColor White }

if ($composeDeploy.ExitCode -ne 0) {
    Write-Host "[ERROR] Docker Compose deployment command failed with exit code $($composeDeploy.ExitCode)." -ForegroundColor Red
    exit $composeDeploy.ExitCode
}

# ---------------------------------------------------------------------------
# 5. Post-Deployment Automated Health Probing & Rollback
# ---------------------------------------------------------------------------
Write-Host "`n[5/5] Performing post-deployment health verification..." -ForegroundColor Yellow
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

if (-not $allHealthy) {
    Write-Host "`n[ERROR] Health verification failed! Application containers did not respond within ${TimeoutSec}s." -ForegroundColor Red
    if ($previousState -and $previousState.ImageTag -and $previousState.ImageTag -ne $ImageTag) {
        Write-Host "Initiating AUTOMATIC ROLLBACK to known-good image tag '$($previousState.ImageTag)'..." -ForegroundColor Yellow
        & (Join-Path $PSScriptRoot "rollback-docker.ps1") -RollbackTag $previousState.ImageTag -Registry $Registry
        exit 1
    } else {
        Write-Host "[WARNING] No previous known-good deployment recorded to rollback to. Manual inspection required." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 6. Record Deployment Record
# ---------------------------------------------------------------------------
Write-Host "`nAll health checks passed successfully!" -ForegroundColor Green

$resolvedCommit = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } elseif ($env:GIT_COMMIT_SHA) { $env:GIT_COMMIT_SHA } else {
    $c = $null
    $origEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'SilentlyContinue'
        $c = & git rev-parse HEAD 2>$null
    } catch {} finally {
        $ErrorActionPreference = $origEap
    }
    $c
}
if (-not $resolvedCommit) { $resolvedCommit = "unknown" }

$deployRecord = [PSCustomObject]@{
    Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    ImageTag  = $ImageTag
    Registry  = $Registry
    Status    = "SUCCESS"
    CommitSha = $resolvedCommit
}

$deployRecord | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8 -Force
$historyFile = Join-Path $historyDir "deployment-history.jsonl"
($deployRecord | ConvertTo-Json -Compress) | Out-File -FilePath $historyFile -Encoding UTF8 -Append

Write-Host "============================================================" -ForegroundColor Green
Write-Host "   Deployment of ArchitectIQ '$ImageTag' Completed: SUCCESS  " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
exit 0
