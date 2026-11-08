<#
.SYNOPSIS
    Runs Gate 1: TruffleHog — Secret Detection.
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
Write-Host "   Executing Gate 1: TruffleHog (Secret Detection)          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& $PyCmd $RunnerPy --gate 1 --mode $Mode
exit $LASTEXITCODE

