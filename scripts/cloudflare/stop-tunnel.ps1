<#
.SYNOPSIS
    Stops the native Windows Cloudflare Quick Tunnel process started by this project.
.DESCRIPTION
    - Reads the stored process ID from logs/cloudflare/tunnel.pid.
    - Verifies the process identity before terminating to prevent affecting unrelated processes.
    - Preserves tunnel logs under logs/cloudflare/tunnel.log.
    - Cleans up runtime PID file safely.
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
Write-Host "         ArchitectIQ Cloudflare Native Tunnel Stopper       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $PidFile)) {
    Write-Host "`n[INFO] No active Cloudflare Tunnel PID file found at $PidFile." -ForegroundColor Yellow
    Write-Host "No tunnel process is currently registered for this project." -ForegroundColor Gray
    exit 0
}

$tunnelPid = (Get-Content $PidFile -ErrorAction SilentlyContinue).Trim()
if (-not ($tunnelPid -match '^\d+$')) {
    Write-Host "`n[WARNING] Invalid or corrupted PID file content. Removing stale file." -ForegroundColor Yellow
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

$proc = Get-Process -Id ([int]$tunnelPid) -ErrorAction SilentlyContinue

if ($proc) {
    # Verify process identity before stopping
    if ($proc.ProcessName -like "*cloudflared*") {
        Write-Host "`nStopping Cloudflare Tunnel process (PID: $tunnelPid)..." -ForegroundColor Yellow
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Start-Sleep -Seconds 1
            Write-Host "Cloudflare Tunnel process (PID: $tunnelPid) has been stopped." -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Failed to stop process: $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "`n[WARNING] Process with PID $tunnelPid is '$($proc.ProcessName)', NOT cloudflared." -ForegroundColor Red
        Write-Host "Aborting stop action to prevent terminating an unrelated application." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[INFO] Cloudflare Tunnel process (PID: $tunnelPid) is already terminated." -ForegroundColor Green
}

# Remove PID file and preserve logs
Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue

Write-Host "`nRuntime state:" -ForegroundColor Cyan
Write-Host "  PID file removed: $PidFile" -ForegroundColor Gray
Write-Host "  Logs preserved:   $LogFile" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

