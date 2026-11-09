<#
.SYNOPSIS
    Runs a single DevSecOps Security Gate (1-5) for ArchitectIQ.
.PARAMETER GateId
    Numeric ID (1-5) of the gate to execute.
.PARAMETER Mode
    STRICT or ADVISORY (default: STRICT)
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateRange(1, 5)]
    [int]$GateId,

    [ValidateSet("STRICT", "ADVISORY")]
    [string]$Mode = "STRICT"
)

$ErrorActionPreference = "Continue"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$VenvPy = Join-Path $RepoRoot "security\.venv\Scripts\python.exe"
$PyCmd = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
$RunnerPy = Join-Path $RepoRoot "security\framework\five_gates_runner.py"

& $PyCmd $RunnerPy --gate $GateId --mode $Mode
exit $LASTEXITCODE

