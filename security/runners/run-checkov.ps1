<#
.SYNOPSIS
    Runs Gate 3: Checkov — Infrastructure as Code Security.
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
$RunnerPy = Join-Path $RepoRoot "security\framework\five_gates_runner.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Executing Gate 3: Checkov (IaC Security)                 " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& $PyCmd $RunnerPy --gate 3 --mode $Mode
exit $LASTEXITCODE

