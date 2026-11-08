<#
.SYNOPSIS
    Reports the status and health of the ArchitectIQ Application containers.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Application Health & Status             " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Container Status
Write-Host "`nDocker Containers:" -ForegroundColor Yellow
$containers = docker ps -a --filter "name=architectiq-backend" --filter "name=architectiq-frontend" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Write-Host $containers

# 2. Endpoint Probes
Write-Host "`nEndpoint Health Probes:" -ForegroundColor Yellow

# Backend health
$backendStatus = "DOWN"
$backendDetail = "Unreachable"
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    $backendStatus = "HEALTHY"
    $backendDetail = "status=$($resp.status), version=$($resp.version)"
} catch {
    $backendDetail = $_.Exception.Message
}

# Frontend health
$frontendStatus = "DOWN"
$frontendDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://localhost" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200) {
        $frontendStatus = "HEALTHY"
        $frontendDetail = "HTTP 200 OK"
    }
} catch {
    $frontendDetail = $_.Exception.Message
}

[PSCustomObject]@{
    Component = "Backend API"
    URL       = "http://localhost:8000/health"
    Status    = $backendStatus
    Detail    = $backendDetail
} | Format-Table -AutoSize

[PSCustomObject]@{
    Component = "Frontend UI"
    URL       = "http://localhost"
    Status    = $frontendStatus
    Detail    = $frontendDetail
} | Format-Table -AutoSize
