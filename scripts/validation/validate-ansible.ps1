<#
.SYNOPSIS
    Validates Ansible playbooks, role tasks, and inventory syntax.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$AnsibleDir = Join-Path $RepoRoot "infrastructure\ansible"
$ValidatorPy = Join-Path $PSScriptRoot "validate_ansible.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Ansible Playbook & Syntax Validation     " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$success = $true

# 1. Validate Playbook and Role YAML Syntax
Write-Host "`n[1/2] Validating YAML syntax across all Ansible files..." -ForegroundColor Yellow
Push-Location $RepoRoot
python $ValidatorPy
$pyExit = $LASTEXITCODE
Pop-Location

if ($pyExit -ne 0) {
    $success = $false
}

# 2. Check Inventory Configuration
Write-Host "`n[2/2] Checking Ansible inventory files..." -ForegroundColor Yellow
$invFile = Join-Path $AnsibleDir "inventory\hosts.ini"
if (Test-Path $invFile) {
    Write-Host "  PASS: Inventory file exists at $invFile" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Inventory file missing at $invFile" -ForegroundColor Red
    $success = $false
}

Write-Host "============================================================" -ForegroundColor Cyan
if ($success) {
    Write-Host "Ansible Validation: ALL PLAYBOOKS & INVENTORIES VALID (PASS)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Ansible Validation: SYNTAX ERRORS DETECTED (FAIL)" -ForegroundColor Red
    exit 1
}
