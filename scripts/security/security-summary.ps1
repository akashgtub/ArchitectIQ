<#
.SYNOPSIS
    ArchitectIQ DevSecOps Security Summary (Delegates to security/scripts/security-summary.ps1)
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $RepoRoot "security\scripts\security-summary.ps1")
