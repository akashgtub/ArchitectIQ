<#
.SYNOPSIS
    ArchitectIQ DevSecOps Single Gate Runner (Delegates to security/scripts/run-single-gate.ps1)
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [int]$GateId,

    [ValidateSet("STRICT", "ADVISORY")]
    [string]$Mode = "STRICT"
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "security\scripts\run-single-gate.ps1") -GateId $GateId -Mode $Mode
