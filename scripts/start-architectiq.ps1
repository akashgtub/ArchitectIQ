<#
.SYNOPSIS
    ArchitectIQ Master Infrastructure and Application Startup Orchestrator
.DESCRIPTION
    Single-command automated launcher for complete DevOps, DevSecOps, monitoring,
    CI/CD, and application environment with safe, idempotent Docker container lifecycle.
    Phases:
      1. Docker Readiness Check and Auto-Launch
      2. Application Stack (Backend and Frontend)
      3. CI/CD Infrastructure (Jenkins Controller and Runner Service)
      4. Monitoring and Observability (Prometheus and Grafana)
      5. DevSecOps Security Infrastructure (SonarQube with Memory Safeguard)
      6. Kubernetes and Infrastructure Tools Verification
      7. Security Scanning Tools Environment Verification
      8. Final Status Dashboard and System Summary
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "               ARCHITECTIQ PLATFORM AND DEVOPS ORCHESTRATOR                     " -ForegroundColor Cyan
Write-Host "           Automated Infrastructure, CI/CD, DevSecOps and App Startup           " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Repository Root: $RepoRoot" -ForegroundColor Gray
Write-Host "Timestamp:       $([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Gray
Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Gray

# ------------------------------------------------------------------------------
# Global Tracking Metrics
# ------------------------------------------------------------------------------
$global:ContainersReused = @()
$global:ContainersCreated = @()
$global:ComponentsSkipped = [ordered]@{}
$global:ManualInterventions = @()

$componentStatus = [ordered]@{
    "Frontend"      = "Pending"
    "Backend"       = "Pending"
    "Jenkins"       = "Pending"
    "Prometheus"    = "Pending"
    "Grafana"       = "Pending"
    "SonarQube"     = "Pending"
    "Kubernetes"    = "Pending"
    "GitHub Runner" = "Pending"
}

# ------------------------------------------------------------------------------
# Helper: Safe Idempotent Container Lifecycle
# ------------------------------------------------------------------------------
function Start-IdempotentContainer {
    param (
        [string]$ContainerName,
        [string]$ComposeFile,
        [string]$ServiceName
    )

    $inspectJson = docker inspect $ContainerName 2>$null
    if ($LASTEXITCODE -eq 0 -and $inspectJson) {
        try {
            $inspectData = $inspectJson | ConvertFrom-Json
            $isRunning = $inspectData.State.Running
            if ($isRunning) {
                Write-Host "  [REUSED] Container '$ContainerName' is already running." -ForegroundColor Green
                $global:ContainersReused += "$ContainerName (running)"
                return "Running"
            } else {
                Write-Host "  [STARTING] Container '$ContainerName' exists but is stopped. Starting via docker start..." -ForegroundColor Yellow
                docker start $ContainerName | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  [REUSED] Container '$ContainerName' started successfully." -ForegroundColor Green
                    $global:ContainersReused += "$ContainerName (started)"
                    return "Running"
                } else {
                    Write-Host "  [ERROR] Failed to start stopped container '$ContainerName'." -ForegroundColor Red
                    return "Failed"
                }
            }
        } catch {
            Write-Host "  [WARNING] Exception reading container inspection for '$ContainerName': $_" -ForegroundColor Yellow
        }
    }

    # Container does not exist - create via Docker Compose
    Write-Host "  [CREATING] Container '$ContainerName' does not exist. Creating via Docker Compose..." -ForegroundColor Yellow
    if ($ComposeFile) {
        if ($ServiceName) {
            docker compose -f $ComposeFile up -d $ServiceName
        } else {
            docker compose -f $ComposeFile up -d
        }
    } else {
        if ($ServiceName) {
            docker compose up -d $ServiceName
        } else {
            docker compose up -d
        }
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [CREATED] Container '$ContainerName' created successfully." -ForegroundColor Green
        $global:ContainersCreated += $ContainerName
        return "Running"
    } else {
        Write-Host "  [ERROR] Docker Compose up failed for container '$ContainerName'." -ForegroundColor Red
        return "Failed"
    }
}

# ==============================================================================
# Phase 1: Docker Engine Readiness Check and Auto-Launch
# ==============================================================================
Write-Host "`n[Phase 1/7] Docker Engine Readiness Check..." -ForegroundColor Yellow

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
$dockerDesktopPaths = @(
    "C:\Program Files\Docker\Docker\Docker Desktop.exe",
    "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
    "$env:ProgramW6432\Docker\Docker\Docker Desktop.exe"
)

$dockerDesktopExe = $null
foreach ($path in $dockerDesktopPaths) {
    if (Test-Path $path) {
        $dockerDesktopExe = $path
        break
    }
}

if (-not $dockerCmd -and -not $dockerDesktopExe) {
    Write-Host "[FATAL] Docker Desktop is not detected on this system." -ForegroundColor Red
    Write-Host "Please install Docker Desktop for Windows to continue." -ForegroundColor Red
    $global:ManualInterventions += "Install Docker Desktop for Windows"
    exit 1
}

$dockerReady = $false
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        Write-Host "  Docker Engine is active and responding." -ForegroundColor Green
    }
} catch {}

if (-not $dockerReady) {
    if ($dockerDesktopExe) {
        Write-Host "  Docker Engine is not running. Launching Docker Desktop ($dockerDesktopExe)..." -ForegroundColor Yellow
        Start-Process -FilePath $dockerDesktopExe
        Write-Host "  Waiting for Docker daemon to become responsive (timeout: 90s)..." -ForegroundColor Yellow
        $waitStart = [DateTime]::UtcNow
        while (([DateTime]::UtcNow - $waitStart).TotalSeconds -lt 90) {
            Start-Sleep -Seconds 3
            try {
                $null = docker info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $dockerReady = $true
                    Write-Host "  Docker Engine is now active and READY." -ForegroundColor Green
                    break
                }
            } catch {}
            Write-Host -NoNewline "."
        }
        Write-Host ""
    }

    if (-not $dockerReady) {
        Write-Host "[FATAL] Docker Engine failed to respond within 90 seconds." -ForegroundColor Red
        Write-Host "Please start Docker Desktop manually and ensure the container daemon is running." -ForegroundColor Red
        $global:ManualInterventions += "Start Docker Desktop manually"
        exit 1
    }
}

# ==============================================================================
# Phase 2: Application Stack (Backend and Frontend)
# ==============================================================================
Write-Host "`n[Phase 2/7] Starting ArchitectIQ Application Stack..." -ForegroundColor Yellow

$backRes = Start-IdempotentContainer -ContainerName "architectiq-backend" -ServiceName "backend"
$frontRes = Start-IdempotentContainer -ContainerName "architectiq-frontend" -ServiceName "frontend"

Write-Host "  Verifying application endpoints..." -ForegroundColor Gray
$backendHealthy = $false
$frontendHealthy = $false

for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    if (-not $backendHealthy) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.status -eq "ok" -or $resp.status -eq "healthy") {
                $backendHealthy = $true
            }
        } catch {}
    }
    if (-not $frontendHealthy) {
        try {
            $web = Invoke-WebRequest -Uri "http://localhost" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($web.StatusCode -eq 200) {
                $frontendHealthy = $true
            }
        } catch {}
    }
    if ($backendHealthy -and $frontendHealthy) { break }
}

$componentStatus["Backend"]  = if ($backendHealthy) { "Running" } else { "Failed" }
$componentStatus["Frontend"] = if ($frontendHealthy) { "Running" } else { "Failed" }
Write-Host "  Backend API (http://localhost:8000):   $($componentStatus['Backend'])" -ForegroundColor $(if ($backendHealthy) { "Green" } else { "Red" })
Write-Host "  Frontend UI (http://localhost):        $($componentStatus['Frontend'])" -ForegroundColor $(if ($frontendHealthy) { "Green" } else { "Red" })

# ==============================================================================
# Phase 3: CI/CD Infrastructure (Jenkins Controller and Runner Service)
# ==============================================================================
Write-Host "`n[Phase 3/7] Starting CI/CD Infrastructure..." -ForegroundColor Yellow

$jenkinsRes = Start-IdempotentContainer -ContainerName "devopsforge-jenkins" -ComposeFile "infrastructure/jenkins/docker-compose.jenkins.yml" -ServiceName "jenkins"

Write-Host "  Verifying Jenkins controller readiness (http://localhost:8081/login)..." -ForegroundColor Gray
$jenkinsHealthy = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $web = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($web.StatusCode -eq 200 -or $web.StatusCode -eq 403) {
            $jenkinsHealthy = $true
            break
        }
    } catch {
        if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 403 -or $_.Exception.Response.StatusCode.value__ -eq 200)) {
            $jenkinsHealthy = $true
            break
        }
    }
}

$componentStatus["Jenkins"] = if ($jenkinsHealthy) { "Running" } else { "Failed" }
Write-Host "  Jenkins CI/CD (http://localhost:8081): $($componentStatus['Jenkins'])" -ForegroundColor $(if ($jenkinsHealthy) { "Green" } else { "Red" })

# Check Windows GitHub Actions Runner Service
Write-Host "  Checking GitHub Actions Runner Windows Service..." -ForegroundColor Gray
$runnerService = Get-Service | Where-Object { $_.Name -like "*runner*" -or $_.DisplayName -like "*actions*runner*" } | Select-Object -First 1
if ($runnerService) {
    if ($runnerService.Status -ne "Running") {
        Write-Host "  Starting GitHub Actions Runner service '$($runnerService.Name)'..." -ForegroundColor Yellow
        try {
            Start-Service -Name $runnerService.Name -ErrorAction Stop
            $componentStatus["GitHub Runner"] = "Running"
        } catch {
            Write-Host "  [WARNING] Could not start runner service: $_" -ForegroundColor Yellow
            $componentStatus["GitHub Runner"] = "Stopped"
            $global:ManualInterventions += "Start Windows Service '$($runnerService.Name)' manually"
        }
    } else {
        $componentStatus["GitHub Runner"] = "Running"
    }
} else {
    $componentStatus["GitHub Runner"] = "Not installed"
    Write-Host "  GitHub Actions Runner Windows service is not registered (Do not register automatically)." -ForegroundColor Gray
}

# ==============================================================================
# Phase 4: Monitoring and Observability (Prometheus and Grafana)
# ==============================================================================
Write-Host "`n[Phase 4/7] Starting Monitoring and Observability Stack..." -ForegroundColor Yellow

$promRes = Start-IdempotentContainer -ContainerName "architectiq-prometheus" -ComposeFile "infrastructure/monitoring/docker-compose.monitoring.yml" -ServiceName "prometheus"
$grafRes = Start-IdempotentContainer -ContainerName "architectiq-grafana" -ComposeFile "infrastructure/monitoring/docker-compose.monitoring.yml" -ServiceName "grafana"

Write-Host "  Verifying Prometheus and Grafana endpoints..." -ForegroundColor Gray
$promHealthy = $false
$grafanaHealthy = $false

for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 2
    if (-not $promHealthy) {
        try {
            $web = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($web.StatusCode -eq 200) { $promHealthy = $true }
        } catch {}
    }
    if (-not $grafanaHealthy) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:3001/api/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.database -eq "ok") { $grafanaHealthy = $true }
        } catch {}
    }
    if ($promHealthy -and $grafanaHealthy) { break }
}

$componentStatus["Prometheus"] = if ($promHealthy) { "Running" } else { "Failed" }
$componentStatus["Grafana"]    = if ($grafanaHealthy) { "Running" } else { "Failed" }
Write-Host "  Prometheus (http://localhost:9090):    $($componentStatus['Prometheus'])" -ForegroundColor $(if ($promHealthy) { "Green" } else { "Red" })
Write-Host "  Grafana (http://localhost:3001):       $($componentStatus['Grafana'])" -ForegroundColor $(if ($grafanaHealthy) { "Green" } else { "Red" })

# ==============================================================================
# Phase 5: DevSecOps Security Infrastructure (SonarQube)
# ==============================================================================
Write-Host "`n[Phase 5/7] Checking DevSecOps Security Infrastructure (SonarQube)..." -ForegroundColor Yellow

$os = Get-CimInstance Win32_OperatingSystem
$freeMB = [math]::Round($os.FreePhysicalMemory / 1024, 0)
$totalMB = [math]::Round($os.TotalVisibleMemorySize / 1024, 0)
$requiredMB = 2560 # 2.5GB RAM requirement for SonarQube and Elasticsearch

Write-Host "  Memory Check: Free Physical RAM = ${freeMB} MB / Total RAM = ${totalMB} MB" -ForegroundColor Gray
if ($freeMB -lt $requiredMB) {
    Write-Host "  [SKIPPED] Insufficient available memory for SonarQube." -ForegroundColor Yellow
    Write-Host "  SonarQube requires at least 2560 MB RAM (Current free: ${freeMB} MB)." -ForegroundColor Yellow
    Write-Host "  Skipping startup safely to preserve system stability and protect running containers." -ForegroundColor DarkYellow
    $componentStatus["SonarQube"] = "Skipped (RAM: ${freeMB}MB < 2560MB)"
    $global:ComponentsSkipped["SonarQube"] = "Available RAM (${freeMB} MB) is below the minimum 2560 MB requirement for SonarQube and its embedded Elasticsearch engine"
} else {
    $sonarRes = Start-IdempotentContainer -ContainerName "architectiq-sonarqube" -ComposeFile "infrastructure/security/docker-compose.security.yml" -ServiceName "sonarqube"
    Write-Host "  Waiting for SonarQube readiness (http://localhost:9000/api/system/status)..." -ForegroundColor Gray
    $sonarHealthy = $false
    for ($i = 1; $i -le 25; $i++) {
        Start-Sleep -Seconds 3
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:9000/api/system/status" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.status -eq "UP") {
                $sonarHealthy = $true
                break
            }
        } catch {}
    }
    $componentStatus["SonarQube"] = if ($sonarHealthy) { "Running" } else { "Failed" }
}
Write-Host "  SonarQube (http://localhost:9000):     $($componentStatus['SonarQube'])" -ForegroundColor $(if ($componentStatus["SonarQube"] -eq "Running") { "Green" } elseif ($componentStatus["SonarQube"] -like "Skipped*") { "Yellow" } else { "Red" })

# ==============================================================================
# Phase 6: Kubernetes and Infrastructure Tools Verification
# ==============================================================================
Write-Host "`n[Phase 6/7] Verifying Kubernetes and Infrastructure Tools..." -ForegroundColor Yellow

$k8sStatus = "Unavailable"
try {
    $nodesOut = kubectl get nodes --request-timeout='3s' 2>&1
    if ($LASTEXITCODE -eq 0 -and $nodesOut -notmatch "error|refused|unable") {
        $k8sStatus = "Ready"
        Write-Host "  Kubernetes Cluster is active and nodes are ready." -ForegroundColor Green
    } else {
        Write-Host "  Kubernetes Cluster is currently unavailable (Docker Desktop K8s not active)." -ForegroundColor Gray
    }
} catch {
    Write-Host "  Kubernetes cluster probe: Unavailable" -ForegroundColor Gray
}
$componentStatus["Kubernetes"] = $k8sStatus

# Verify local IaC and automation tools
$toolsReport = @()
try {
    $tfVer = (terraform version 2>$null | Select-Object -First 1)
    if ($tfVer) { $toolsReport += "Terraform ($tfVer)" }
} catch {}

try {
    $ansibleVer = (ansible --version 2>$null | Select-Object -First 1)
    if ($ansibleVer) { $toolsReport += "Ansible ($ansibleVer)" }
} catch {}

try {
    $pyVer = (python --version 2>$null)
    if ($pyVer) { $toolsReport += "Python ($pyVer)" }
} catch {}

try {
    $gitVer = (git --version 2>$null)
    if ($gitVer) { $toolsReport += "Git ($gitVer)" }
} catch {}

Write-Host "  Verified Local Tools: $($toolsReport -join ', ')" -ForegroundColor Cyan

# ==============================================================================
# Phase 7: Security Scanning Tools Environment Verification
# ==============================================================================
Write-Host "`n[Phase 7/7] Preparing DevSecOps Security Scanning Environment..." -ForegroundColor Yellow
Write-Host "  (Checking tool readiness only - scans will NOT be executed during startup)" -ForegroundColor Gray

$scanners = [ordered]@{
    "1. TruffleHog (Secret Detection)"     = "Unavailable"
    "2. Bandit (Python SAST)"              = "Unavailable"
    "3. Checkov (IaC Security)"            = "Unavailable"
    "4. Hadolint (Dockerfile Security)"    = "Unavailable"
    "5. Snyk (Dependency Vulnerabilities)" = "Unavailable"
    "6. OWASP ZAP (DAST Baseline)"         = "Unavailable"
    "7. SonarQube Scanner (Code Quality)"  = "Unavailable"
}

# 1. TruffleHog
if (Get-Command trufflehog -ErrorAction SilentlyContinue) {
    $scanners["1. TruffleHog (Secret Detection)"] = "Ready (CLI installed)"
}

# 2. Bandit
$banditPath = Join-Path $RepoRoot "security\.venv\Scripts\bandit.exe"
if (Test-Path $banditPath) {
    $scanners["2. Bandit (Python SAST)"] = "Ready (Virtualenv installed)"
} elseif (Get-Command bandit -ErrorAction SilentlyContinue) {
    $scanners["2. Bandit (Python SAST)"] = "Ready (CLI installed)"
}

# 3. Checkov
$checkovPath = Join-Path $RepoRoot "security\.venv\Scripts\checkov.cmd"
if (Test-Path $checkovPath) {
    $scanners["3. Checkov (IaC Security)"] = "Ready (Virtualenv installed)"
} elseif (Get-Command checkov -ErrorAction SilentlyContinue) {
    $scanners["3. Checkov (IaC Security)"] = "Ready (CLI installed)"
}

# 4. Hadolint
if (Get-Command hadolint -ErrorAction SilentlyContinue) {
    $scanners["4. Hadolint (Dockerfile Security)"] = "Ready (CLI installed)"
}

# 5. Snyk
if (Get-Command snyk -ErrorAction SilentlyContinue) {
    $scanners["5. Snyk (Dependency Vulnerabilities)"] = "Ready (CLI installed)"
}

# 6. OWASP ZAP
$zapRunner = Join-Path $RepoRoot "security\runners\run-zap.ps1"
if (Test-Path $zapRunner) {
    $scanners["6. OWASP ZAP (DAST Baseline)"] = "Ready (Framework runner available)"
}

# 7. SonarQube Scanner
if (Get-Command sonar-scanner -ErrorAction SilentlyContinue) {
    $scanners["7. SonarQube Scanner (Code Quality)"] = "Ready (CLI installed)"
}

foreach ($item in $scanners.GetEnumerator()) {
    $k = $item.Key
    $v = $item.Value
    $c = if ($v -like "Ready*") { "Green" } else { "Yellow" }
    Write-Host "  - ${k}: ${v}" -ForegroundColor $c
}

# ==============================================================================
# Phase 8: Final Status Dashboard and System Summary
# ==============================================================================
Write-Host "`n"
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "                    ARCHITECTIQ PLATFORM STATUS DASHBOARD                       " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$dashboardTable = @(
    [PSCustomObject]@{ Component = "Frontend";      "Expected URL" = "http://localhost";      Status = $componentStatus["Frontend"] }
    [PSCustomObject]@{ Component = "Backend";       "Expected URL" = "http://localhost:8000"; Status = $componentStatus["Backend"] }
    [PSCustomObject]@{ Component = "Jenkins";       "Expected URL" = "http://localhost:8081"; Status = $componentStatus["Jenkins"] }
    [PSCustomObject]@{ Component = "Prometheus";    "Expected URL" = "http://localhost:9090"; Status = $componentStatus["Prometheus"] }
    [PSCustomObject]@{ Component = "Grafana";       "Expected URL" = "http://localhost:3001"; Status = $componentStatus["Grafana"] }
    [PSCustomObject]@{ Component = "SonarQube";     "Expected URL" = "http://localhost:9000"; Status = $componentStatus["SonarQube"] }
    [PSCustomObject]@{ Component = "Kubernetes";    "Expected URL" = "kubectl get nodes";     Status = $componentStatus["Kubernetes"] }
    [PSCustomObject]@{ Component = "GitHub Runner"; "Expected URL" = "Windows Service";       Status = $componentStatus["GitHub Runner"] }
)

$dashboardTable | Format-Table -AutoSize | Out-String | Write-Host -ForegroundColor White

Write-Host "--------------------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "[SYSTEM METRICS AND EXECUTION SUMMARY]" -ForegroundColor Cyan
Write-Host "Docker Status:            Active (Engine responding)" -ForegroundColor Green
Write-Host "Total Memory:             $totalMB MB" -ForegroundColor White
Write-Host "Available Memory:         $freeMB MB" -ForegroundColor Yellow

$reusedStr = if ($global:ContainersReused.Count -gt 0) { $global:ContainersReused -join ", " } else { "None" }
$createdStr = if ($global:ContainersCreated.Count -gt 0) { $global:ContainersCreated -join ", " } else { "None" }
Write-Host "Containers Reused:        $reusedStr" -ForegroundColor Green
Write-Host "Containers Newly Created: $createdStr" -ForegroundColor Cyan

if ($global:ComponentsSkipped.Count -gt 0) {
    Write-Host "`nComponents Skipped:" -ForegroundColor Yellow
    foreach ($item in $global:ComponentsSkipped.GetEnumerator()) {
        Write-Host "  * $($item.Key): $($item.Value)" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "Components Skipped:       None" -ForegroundColor Green
}

if ($global:ManualInterventions.Count -gt 0) {
    Write-Host "`nComponents Requiring Manual Intervention:" -ForegroundColor Red
    foreach ($item in $global:ManualInterventions) {
        Write-Host "  ! $item" -ForegroundColor Red
    }
} else {
    Write-Host "Manual Interventions:     None required" -ForegroundColor Green
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ArchitectIQ platform startup sequence completed." -ForegroundColor Green
Write-Host "Security scans remain available on demand via scripts/security/run-all-gates.ps1" -ForegroundColor Gray
Write-Host "================================================================================" -ForegroundColor Cyan
