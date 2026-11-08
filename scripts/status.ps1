<#
.SYNOPSIS
    ArchitectIQ Application Status Checker (Delegates to scripts/application/app-status.ps1)
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "application\app-status.ps1")
