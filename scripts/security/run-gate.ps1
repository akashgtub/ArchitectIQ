<#
.SYNOPSIS
    Runs a single DevSecOps Security Gate (1-12) for ArchitectIQ.
.PARAMETER GateId
    Numeric ID (1-12) or string ID of the gate to execute.
#>
param (
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$GateId
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host ">>> Executing DevSecOps Security Gate: $GateId" -ForegroundColor Cyan

python (Join-Path $RepoRoot "security\framework\runner.py") --gate $GateId
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ">>> Gate $GateId execution completed successfully." -ForegroundColor Green
} else {
    Write-Host ">>> Gate $GateId reported issues or failed (Exit code: $exitCode)." -ForegroundColor Yellow
}

exit $exitCode

