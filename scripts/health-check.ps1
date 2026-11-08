<#
.SYNOPSIS
    ArchitectIQ Platform Health Check (Delegates to scripts/health/check-all-services.ps1)
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "health\check-all-services.ps1")
