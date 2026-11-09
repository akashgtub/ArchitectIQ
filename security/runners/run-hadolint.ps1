<#
.SYNOPSIS
    Runs Gate 4: Hadolint — Dockerfile Security Linting.
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
Write-Host "   Executing Gate 4: Hadolint (Dockerfile Linting)          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& $PyCmd $RunnerPy --gate 4 --mode $Mode
exit $LASTEXITCODE

