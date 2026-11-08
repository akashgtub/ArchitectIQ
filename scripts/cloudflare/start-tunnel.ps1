<#
.SYNOPSIS
    Starts a native Windows Cloudflare Quick Tunnel forwarding traffic exclusively to Jenkins on port 8081.
.DESCRIPTION
    - Verifies Jenkins is running locally on port 8081 before starting.
    - Runs the native Windows cloudflared.exe binary (no Docker container).
    - Exposes http://127.0.0.1:8081 ONLY (Jenkins). Application, Prometheus, Grafana, and SonarQube remain isolated.
    - Prevents duplicate tunnel processes.
    - Captures the temporary trycloudflare.com URL and stores PID in logs/cloudflare/tunnel.pid.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

$LogsDir = Join-Path $RepoRoot "logs\cloudflare"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$PidFile = Join-Path $LogsDir "tunnel.pid"
$LogFile = Join-Path $LogsDir "tunnel.log"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         ArchitectIQ Cloudflare Native Tunnel Launcher       " -ForegroundColor Cyan
Write-Host "               Secure Jenkins CI/CD Webhook Tunnel          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Locate Native cloudflared Executable
Write-Host "`n[1/4] Checking cloudflared binary..." -ForegroundColor Yellow
$cloudflaredCmd = $null

if (Get-Command "cloudflared" -ErrorAction SilentlyContinue) {
    $cloudflaredCmd = (Get-Command "cloudflared").Source
} elseif (Test-Path "C:\Program Files (x86)\cloudflared\cloudflared.exe") {
    $cloudflaredCmd = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
} elseif (Test-Path "C:\Program Files\cloudflared\cloudflared.exe") {
    $cloudflaredCmd = "C:\Program Files\cloudflared\cloudflared.exe"
}

if (-not $cloudflaredCmd -or -not (Test-Path $cloudflaredCmd)) {
    Write-Host "[ERROR] Native cloudflared.exe not found on system." -ForegroundColor Red
    Write-Host "Please install cloudflared using winget:" -ForegroundColor Yellow
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor White
    exit 1
}

$versionInfo = & $cloudflaredCmd --version
Write-Host "Found: $cloudflaredCmd" -ForegroundColor Green
Write-Host "Version: $versionInfo" -ForegroundColor Gray

# 2. Verify Jenkins is Running and Responding Locally on Port 8081
Write-Host "`n[2/4] Verifying Jenkins availability on port 8081..." -ForegroundColor Yellow
$jenkinsOnline = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200 -or $resp.StatusCode -eq 403) {
        $jenkinsOnline = $true
    }
} catch {
    if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 200 -or $_.Exception.Response.StatusCode.value__ -eq 403)) {
        $jenkinsOnline = $true
    }
}

if (-not $jenkinsOnline) {
    Write-Host "[ERROR] Jenkins is not responding on http://127.0.0.1:8081." -ForegroundColor Red
    Write-Host "Please start the Jenkins controller before launching the tunnel:" -ForegroundColor Yellow
    Write-Host "  powershell.exe -File scripts\jenkins\start-jenkins.ps1" -ForegroundColor White
    exit 1
}
Write-Host "Jenkins is healthy and responding locally on port 8081." -ForegroundColor Green

# 3. Check for Duplicate or Existing Running Tunnel
Write-Host "`n[3/4] Checking for existing tunnel process..." -ForegroundColor Yellow
if (Test-Path $PidFile) {
    $existingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue).Trim()
    if ($existingPid -match '^\d+$') {
        $existingProc = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($existingProc -and $existingProc.ProcessName -like "*cloudflared*") {
            Write-Host "[INFO] A Cloudflare Tunnel is ALREADY RUNNING (PID: $existingPid)." -ForegroundColor Green
            if (Test-Path $LogFile) {
                $urlMatch = Select-String -Path $LogFile -Pattern 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | Select-Object -Last 1
                if ($urlMatch) {
                    Write-Host "Public Tunnel URL:  $($urlMatch.Matches.Value)" -ForegroundColor Cyan
                    Write-Host "Target Forwarding:  http://127.0.0.1:8081 (Jenkins ONLY)" -ForegroundColor White
                    Write-Host "Webhook Endpoint:   $($urlMatch.Matches.Value)/github-webhook/" -ForegroundColor Cyan
                }
            }
            Write-Host "To stop the running tunnel, use: scripts\cloudflare\stop-tunnel.ps1" -ForegroundColor Yellow
            exit 0
        }
    }
    # Clean up stale PID file
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}

# 4. Launch Native cloudflared Process
Write-Host "`n[4/4] Starting native cloudflared Quick Tunnel process..." -ForegroundColor Yellow
Write-Host "Forwarding traffic strictly to: http://127.0.0.1:8081" -ForegroundColor Gray
Write-Host "Log file: $LogFile" -ForegroundColor Gray

# Clear previous log to capture clean new URL
if (Test-Path $LogFile) {
    Remove-Item -Path $LogFile -Force -ErrorAction SilentlyContinue
}

$proc = Start-Process -FilePath $cloudflaredCmd `
    -ArgumentList "tunnel --url http://127.0.0.1:8081 --no-autoupdate" `
    -RedirectStandardError $LogFile `
    -PassThru `
    -WindowStyle Hidden

$tunnelPid = $proc.Id
Set-Content -Path $PidFile -Value $tunnelPid -Force

Write-Host "Cloudflare tunnel process launched (PID: $tunnelPid)." -ForegroundColor Green

# 5. Wait and Extract Public trycloudflare.com URL
Write-Host "Waiting for Cloudflare edge tunnel URL..." -ForegroundColor Yellow
$publicUrl = $null

for ($i = 1; $i -le 25; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $LogFile) {
        try {
            $content = Get-Content -Path $LogFile -Raw -ErrorAction SilentlyContinue
            if ($content -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
                $publicUrl = $matches[1]
                break
            }
        } catch {}
    }
    if ($publicUrl) { break }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
if ($publicUrl) {
    Write-Host "   Cloudflare Quick Tunnel Successfully Established!        " -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "Public Tunnel URL:  $publicUrl" -ForegroundColor Green
    Write-Host "Target Service:     http://127.0.0.1:8081 (Jenkins CI/CD ONLY)" -ForegroundColor White
    Write-Host "Webhook URL:        $publicUrl/github-webhook/" -ForegroundColor Cyan
    Write-Host "Tunnel PID:         $tunnelPid" -ForegroundColor Gray
    Write-Host "Logs Location:      $LogFile" -ForegroundColor Gray
    Write-Host "------------------------------------------------------------" -ForegroundColor Gray
    Write-Host "IMPORTANT NOTICE:" -ForegroundColor Yellow
    Write-Host "  * Quick Tunnel URLs are temporary and will expire when stopped." -ForegroundColor Yellow
    Write-Host "  * Only Jenkins (port 8081) is accessible through this tunnel." -ForegroundColor Yellow
    Write-Host "  * Application frontend/backend, Prometheus, and Grafana remain safe and isolated." -ForegroundColor Yellow
    Write-Host "  * To stop the tunnel at any time, run: scripts\cloudflare\stop-tunnel.ps1" -ForegroundColor Yellow
} else {
    Write-Host "[WARNING] Tunnel started (PID: $tunnelPid), but the public URL could not be detected yet." -ForegroundColor Yellow
    Write-Host "Please check the log file: $LogFile" -ForegroundColor Gray
}
Write-Host "============================================================" -ForegroundColor Cyan
