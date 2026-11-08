<#
.SYNOPSIS
    ArchitectIQ Application Stack Stopper (Delegates to scripts/application/stop-app.ps1)
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot "application\stop-app.ps1")
