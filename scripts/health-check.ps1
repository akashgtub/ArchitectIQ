# scripts/health-check.ps1
# Runs detailed health checks against all ArchitectIQ application and monitoring endpoints

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "          ArchitectIQ Health Verification Probe     " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

$allPassed = $true

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus = 200,
        [string]$ExpectedSubstr = $null
    )
    Write-Host "Testing $Name ($Url)..." -NoNewline
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq $ExpectedStatus) {
            if ($null -ne $ExpectedSubstr -and -not ($resp.Content -match $ExpectedSubstr)) {
                Write-Host " [FAILED: Missing expected body token]" -ForegroundColor Red
                return $false
            }
            Write-Host " [PASS: HTTP $($resp.StatusCode)]" -ForegroundColor Green
            return $true
        } else {
            Write-Host " [FAILED: HTTP $($resp.StatusCode)]" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host " [ERROR: $($_.Exception.Message)]" -ForegroundColor Red
        return $false
    }
}

# Run tests
if (-not (Test-Endpoint -Name "Backend /health" -Url "http://localhost:8000/health" -ExpectedSubstr 'healthy')) { $allPassed = $false }
if (-not (Test-Endpoint -Name "Backend /api/v1/health" -Url "http://localhost:8000/api/v1/health" -ExpectedSubstr 'healthy')) { $allPassed = $false }
if (-not (Test-Endpoint -Name "Backend /metrics" -Url "http://localhost:8000/metrics" -ExpectedSubstr 'architectiq_http_requests_total')) { $allPassed = $false }
if (-not (Test-Endpoint -Name "Frontend /healthz" -Url "http://localhost/healthz" -ExpectedSubstr 'healthy')) { $allPassed = $false }
if (-not (Test-Endpoint -Name "Prometheus /-/healthy" -Url "http://localhost:9090/-/healthy" -ExpectedSubstr 'Prometheus Server is Healthy.')) { $allPassed = $false }
if (-not (Test-Endpoint -Name "Grafana /api/health" -Url "http://localhost:3001/api/health" -ExpectedSubstr '"database": "ok"')) { $allPassed = $false }

Write-Host "`n----------------------------------------------------"
if ($allPassed) {
    Write-Host "Overall Health Verification: ALL CHECKS PASSED (HEALTHY)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Overall Health Verification: ONE OR MORE CHECKS FAILED" -ForegroundColor Red
    exit 1
}
