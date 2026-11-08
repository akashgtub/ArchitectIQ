<#
.SYNOPSIS
    Runs all 7 DevSecOps Security Gates and aggregates the security summary.
.PARAMETER Mode
    STRICT or ADVISORY (default: STRICT)
#>
param(
    [ValidateSet("STRICT", "ADVISORY")]
    [string]$Mode = "STRICT"
)

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPy = Join-Path $RepoRoot "security\.venv\Scripts\python.exe"
$PyCmd = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
$RunnerPy = Join-Path $RepoRoot "security\framework\seven_gates_runner.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "      ARCHITECTIQ 7 ESSENTIAL DEVSECOPS GATES RUNNER        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Enforcement Mode: $Mode" -ForegroundColor Yellow

& $PyCmd $RunnerPy --all --mode $Mode
$exitCode = $LASTEXITCODE

Write-Host "`n============================================================" -ForegroundColor Cyan
if ($exitCode -eq 0) {
    Write-Host "Security Framework Execution: COMPLETED (PASS)" -ForegroundColor Green
} else {
    Write-Host "Security Framework Execution: QUALITY GATES BLOCKED / FAILED (FAIL)" -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor Cyan

exit $exitCode

