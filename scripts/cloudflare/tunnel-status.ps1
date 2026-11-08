<#
.SYNOPSIS
    Reports the status, health, and URL of the native Cloudflare Quick Tunnel.
.DESCRIPTION
    - Verifies cloudflared binary installation and version.
    - Checks process status from logs/cloudflare/tunnel.pid.
    - Extracts temporary trycloudflare.com URL from logs.
    - Probes local Jenkins connectivity on port 8081.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

$LogsDir = Join-Path $RepoRoot "logs\cloudflare"
$PidFile = Join-Path $LogsDir "tunnel.pid"
$LogFile = Join-Path $LogsDir "tunnel.log"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         ArchitectIQ Cloudflare Native Tunnel Status         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Binary Installation Check
Write-Host "`nBinary Installation:" -ForegroundColor Yellow
$cloudflaredCmd = $null
if (Get-Command "cloudflared" -ErrorAction SilentlyContinue) {
    $cloudflaredCmd = (Get-Command "cloudflared").Source
} elseif (Test-Path "C:\Program Files (x86)\cloudflared\cloudflared.exe") {
    $cloudflaredCmd = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
} elseif (Test-Path "C:\Program Files\cloudflared\cloudflared.exe") {
    $cloudflaredCmd = "C:\Program Files\cloudflared\cloudflared.exe"
}

$cfInstalled = [bool]$cloudflaredCmd
$cfVersion = "N/A"
if ($cfInstalled) {
    $verOut = & $cloudflaredCmd --version 2>&1
    if ($verOut -match 'cloudflared version (\S+)') {
        $cfVersion = $matches[1]
    } else {
        $cfVersion = ($verOut | Select-Object -First 1)
    }
}

Write-Host "  Installed:     $($cfInstalled)" -ForegroundColor $(if ($cfInstalled) { "Green" } else { "Red" })
Write-Host "  Path:          $cloudflaredCmd" -ForegroundColor Gray
Write-Host "  Version:       $cfVersion" -ForegroundColor Gray

# 2. Process Status Check
Write-Host "`nTunnel Process Status:" -ForegroundColor Yellow
$isRunning = $false
$tunnelPid = "N/A"
$publicUrl = "N/A"

if (Test-Path $PidFile) {
    $storedPid = (Get-Content $PidFile -ErrorAction SilentlyContinue).Trim()
    if ($storedPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$storedPid) -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -like "*cloudflared*") {
            $isRunning = $true
            $tunnelPid = $storedPid
        }
    }
}

if (Test-Path $LogFile) {
    try {
        $lines = Get-Content -Path $LogFile -Tail 50 -ErrorAction SilentlyContinue
        foreach ($line in $lines) {
            if ($line -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
                $publicUrl = $matches[1]
            }
        }
    } catch {}
}

Write-Host "  Tunnel State:  $($(if ($isRunning) { "RUNNING" } else { "STOPPED" }))" -ForegroundColor $(if ($isRunning) { "Green" } else { "Yellow" })
Write-Host "  Process ID:    $tunnelPid" -ForegroundColor Gray
Write-Host "  Local Target:  http://127.0.0.1:8081 (Jenkins ONLY)" -ForegroundColor White
Write-Host "  Public URL:    $publicUrl" -ForegroundColor $(if ($isRunning -and $publicUrl -ne "N/A") { "Cyan" } else { "Gray" })

if ($isRunning -and $publicUrl -ne "N/A") {
    Write-Host "  Webhook URL:   $publicUrl/github-webhook/" -ForegroundColor Cyan
}

# 3. Local Jenkins Service Connectivity Probe
Write-Host "`nLocal Jenkins Connectivity (Port 8081):" -ForegroundColor Yellow
$jenkinsStatus = "DOWN"
$jenkinsDetail = "Port 8081 unreachable"
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200 -or $resp.StatusCode -eq 403) {
        $jenkinsStatus = "HEALTHY"
        $jenkinsDetail = "HTTP $($resp.StatusCode) - Ready"
    }
} catch {
    if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 200 -or $_.Exception.Response.StatusCode.value__ -eq 403)) {
        $jenkinsStatus = "HEALTHY"
        $jenkinsDetail = "HTTP $($_.Exception.Response.StatusCode.value__) - Ready"
    } else {
        $jenkinsDetail = $_.Exception.Message
    }
}

Write-Host "  Jenkins State: $jenkinsStatus ($jenkinsDetail)" -ForegroundColor $(if ($jenkinsStatus -eq "HEALTHY") { "Green" } else { "Red" })

Write-Host "`nSummary Table:" -ForegroundColor Yellow
[PSCustomObject]@{
    Component      = "Cloudflare Quick Tunnel"
    ExecutionMode  = "Native Windows (cloudflared.exe)"
    State          = if ($isRunning) { "RUNNING" } else { "STOPPED" }
    PID            = $tunnelPid
    Target         = "http://127.0.0.1:8081"
    PublicURL      = $publicUrl
    JenkinsStatus  = $jenkinsStatus
} | Format-List
Write-Host "============================================================" -ForegroundColor Cyan

