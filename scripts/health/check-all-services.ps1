<#
.SYNOPSIS
    Performs comprehensive end-to-end health check across all ArchitectIQ components:
    Application, Monitoring Stack, CI/CD Jenkins, and Kubernetes cluster.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Comprehensive Platform Health Audit      " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$services = @()

# 1. Backend Application
$bStatus = "DOWN"
$bDetail = "Unreachable"
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    $bStatus = "HEALTHY"
    $bDetail = "status=$($resp.status)"
} catch {
    $bDetail = $_.Exception.Message
}
$services += [PSCustomObject]@{ Component = "App: Backend API"; Port = 8000; Status = $bStatus; Detail = $bDetail }

# 2. Frontend Application
$fStatus = "DOWN"
$fDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://localhost" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200) {
        $fStatus = "HEALTHY"
        $fDetail = "HTTP 200 OK"
    }
} catch {
    $fDetail = $_.Exception.Message
}
$services += [PSCustomObject]@{ Component = "App: Frontend UI"; Port = 80; Status = $fStatus; Detail = $fDetail }

# 3. Prometheus
$pStatus = "DOWN"
$pDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200) {
        $pStatus = "HEALTHY"
        $pDetail = "Prometheus is Healthy"
    }
} catch {
    $pDetail = $_.Exception.Message
}
$services += [PSCustomObject]@{ Component = "Monitoring: Prometheus"; Port = 9090; Status = $pStatus; Detail = $pDetail }

# 4. Grafana
$gStatus = "DOWN"
$gDetail = "Unreachable"
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:3001/api/health" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($resp.database -eq "ok") {
        $gStatus = "HEALTHY"
        $gDetail = "database=ok, v=$($resp.version)"
    }
} catch {
    $gDetail = $_.Exception.Message
}
$services += [PSCustomObject]@{ Component = "Monitoring: Grafana"; Port = 3001; Status = $gStatus; Detail = $gDetail }

# 5. Jenkins CI/CD
$jStatus = "DOWN"
$jDetail = "Unreachable"
try {
    $web = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200 -or $web.StatusCode -eq 403) {
        $jStatus = "HEALTHY"
        $jDetail = "HTTP 200/403 Ready"
    }
} catch {
    if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 403 -or $_.Exception.Response.StatusCode.value__ -eq 200)) {
        $jStatus = "HEALTHY"
        $jDetail = "HTTP Ready"
    } else {
        $jDetail = $_.Exception.Message
    }
}
$services += [PSCustomObject]@{ Component = "CI/CD: Jenkins"; Port = 8081; Status = $jStatus; Detail = $jDetail }

# 6. Kubernetes Cluster
$kStatus = "OFFLINE"
$kDetail = "Unreachable"
try {
    $node = kubectl get nodes --request-timeout=3s -o jsonpath='{.items[0].metadata.name}' 2>$null
    if ($LASTEXITCODE -eq 0 -and $node) {
        $kStatus = "HEALTHY"
        $kDetail = "Node: $node"
    }
} catch {}
$services += [PSCustomObject]@{ Component = "Cluster: Kubernetes"; Port = "6443"; Status = $kStatus; Detail = $kDetail }

# 7. Cloudflare Quick Tunnel (Native Windows)
$cfStatus = "STOPPED"
$cfDetail = "Tunnel offline"
$cfPidFile = Join-Path $RepoRoot "logs\cloudflare\tunnel.pid"
if (Test-Path $cfPidFile) {
    $cfPid = (Get-Content $cfPidFile -ErrorAction SilentlyContinue).Trim()
    if ($cfPid -match '^\d+$') {
        $cfProc = Get-Process -Id ([int]$cfPid) -ErrorAction SilentlyContinue
        if ($cfProc -and $cfProc.ProcessName -like "*cloudflared*") {
            $cfStatus = "HEALTHY"
            $cfDetail = "Running (PID: $cfPid -> 127.0.0.1:8081)"
        }
    }
}
$services += [PSCustomObject]@{ Component = "Tunnel: Cloudflare"; Port = "Native"; Status = $cfStatus; Detail = $cfDetail }

Write-Host "`nPlatform Component Status Table:" -ForegroundColor Yellow
$services | Format-Table -AutoSize

Write-Host "Summary: $(($services | Where-Object { $_.Status -eq 'HEALTHY' }).Count) of $($services.Count) components HEALTHY." -ForegroundColor Cyan

