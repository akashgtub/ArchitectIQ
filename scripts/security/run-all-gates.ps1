<#
.SYNOPSIS
    ArchitectIQ DevSecOps All-Gates Runner (Delegates to security/scripts/run-all-gates.ps1)
#>
param(
    [ValidateSet("STRICT", "ADVISORY")]
    [string]$Mode = "STRICT"
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "security\scripts\run-all-gates.ps1") -Mode $Mode
