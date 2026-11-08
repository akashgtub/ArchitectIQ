<#
.SYNOPSIS
    ArchitectIQ Project Validation Suite.
    Runs Docker, Terraform, Kubernetes, and Ansible validations.
#>
$ErrorActionPreference = "Continue"

$PDir = Join-Path $PSScriptRoot "validation"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "        ARCHITECTIQ ENTERPRISE VALIDATION SUITE             " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& (Join-Path $PDir "validate-docker.ps1")
& (Join-Path $PDir "validate-terraform.ps1")
& (Join-Path $PDir "validate-kubernetes.ps1")
& (Join-Path $PDir "validate-ansible.ps1")

Write-Host "`nAll validation checks completed." -ForegroundColor Green
