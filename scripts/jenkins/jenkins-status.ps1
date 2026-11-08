<#
.SYNOPSIS
    Reports the status and responsiveness of the Jenkins CI/CD controller.
#>
$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Jenkins CI/CD Controller Health          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Container Status
Write-Host "`nDocker Containers:" -ForegroundColor Yellow
$containers = docker ps -a --filter "name=devopsforge-jenkins" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Write-Host $containers

# 2. Endpoint Probe
Write-Host "`nEndpoint Health Probe:" -ForegroundColor Yellow

$jenkinsStatus = "DOWN"
$jenkinsDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200 -or $web.StatusCode -eq 403) {
        $jenkinsStatus = "HEALTHY"
        $jenkinsDetail = "HTTP $($web.StatusCode) - Ready"
    }
} catch {
    if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 403 -or $_.Exception.Response.StatusCode.value__ -eq 200)) {
        $jenkinsStatus = "HEALTHY"
        $jenkinsDetail = "HTTP $($_.Exception.Response.StatusCode.value__) - Ready"
    } else {
        $jenkinsDetail = $_.Exception.Message
    }
}

[PSCustomObject]@{
    Component = "Jenkins Controller"
    URL       = "http://localhost:8081"
    Status    = $jenkinsStatus
    Detail    = $jenkinsDetail
} | Format-Table -AutoSize
