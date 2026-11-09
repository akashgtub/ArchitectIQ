<#
.SYNOPSIS
    Runs Gate 5: OWASP ZAP — Dynamic Application Security Testing (DAST).
.PARAMETER Mode
    STRICT or ADVISORY (default: STRICT)
.PARAMETER TargetUrl
    Target URL of running ArchitectIQ test environment (default: http://localhost:8000)
#>
param(
    [ValidateSet("STRICT", "ADVISORY")]
    [string]$Mode = "STRICT",
    [string]$TargetUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPy = Join-Path $RepoRoot "security\.venv\Scripts\python.exe"
$PyCmd = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
$RunnerPy = Join-Path $RepoRoot "security\framework\five_gates_runner.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Executing Gate 5: OWASP ZAP (DAST Baseline Testing)      " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Target Environment: $TargetUrl" -ForegroundColor Yellow

& $PyCmd $RunnerPy --gate 5 --mode $Mode --target-url $TargetUrl
exit $LASTEXITCODE

