<#
.SYNOPSIS
    Validates Terraform Infrastructure as Code configurations.
    Does NOT run terraform apply or terraform destroy.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$TfDir = Join-Path $RepoRoot "infrastructure\terraform"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Terraform Configuration Validation       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$success = $true
$env:CHECKPOINT_DISABLE = "1"

# 1. Format Check
Write-Host "`n[1/2] Checking Terraform formatting (fmt -check)..." -ForegroundColor Yellow
Push-Location $TfDir
$fmtOut = terraform fmt -check 2>&1
$fmtExit = $LASTEXITCODE
if ($fmtExit -eq 0) {
    Write-Host "  PASS: Terraform files are properly formatted." -ForegroundColor Green
} else {
    Write-Host "  WARN: Some files require formatting:`n$fmtOut" -ForegroundColor Yellow
}

# 2. Configuration Validation
Write-Host "`n[2/2] Validating Terraform configuration syntax..." -ForegroundColor Yellow
$valOut = terraform validate 2>&1
$valExit = $LASTEXITCODE
Pop-Location

if ($valExit -eq 0) {
    Write-Host "  PASS: $valOut" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Terraform validation error:`n$valOut" -ForegroundColor Red
    $success = $false
}

Write-Host "============================================================" -ForegroundColor Cyan
if ($success) {
    Write-Host "Terraform Validation: SUCCESSFUL (PASS)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Terraform Validation: FAILED (FAIL)" -ForegroundColor Red
    exit 1
}
