<#
.SYNOPSIS
    Reports the status and health of the Prometheus and Grafana monitoring stack.
#>
$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Monitoring Health & Status               " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Container Status
Write-Host "`nDocker Containers:" -ForegroundColor Yellow
$containers = docker ps -a --filter "name=architectiq-prometheus" --filter "name=architectiq-grafana" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Write-Host $containers

# 2. Endpoint Probes
Write-Host "`nEndpoint Health Probes:" -ForegroundColor Yellow

$promStatus = "DOWN"
$promDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200) {
        $promStatus = "HEALTHY"
        $promDetail = "Prometheus is Healthy"
    }
} catch {
    $promDetail = $_.Exception.Message
}

$grafanaStatus = "DOWN"
$grafanaDetail = "Unreachable"
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:3001/api/health" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($resp.database -eq "ok") {
        $grafanaStatus = "HEALTHY"
        $grafanaDetail = "database=ok, version=$($resp.version)"
    }
} catch {
    $grafanaDetail = $_.Exception.Message
}

[PSCustomObject]@{
    Component = "Prometheus"
    URL       = "http://localhost:9090/-/healthy"
    Status    = $promStatus
    Detail    = $promDetail
} | Format-Table -AutoSize

[PSCustomObject]@{
    Component = "Grafana"
    URL       = "http://localhost:3001/api/health"
    Status    = $grafanaStatus
    Detail    = $grafanaDetail
} | Format-Table -AutoSize

