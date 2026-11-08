<#
.SYNOPSIS
    Stops the Jenkins CI/CD controller container.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Jenkins CI/CD Controller Stopper          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "Stopping Jenkins controller container..." -ForegroundColor Yellow
docker compose -f infrastructure/jenkins/docker-compose.jenkins.yml stop

Write-Host "Jenkins container stopped." -ForegroundColor Green

