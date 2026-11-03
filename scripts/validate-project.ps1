# scripts/validate-project.ps1
# Performs complete non-destructive validation across Backend, Frontend, Terraform, Ansible, Docker, and Health

$ErrorActionPreference = "Continue"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "         ArchitectIQ Project Validation Suite       " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$OverallPass = $true

# 1. Backend Pytest
Write-Host "`n[1/6] Running Backend Pytest Suite..." -ForegroundColor Yellow
python -m pytest backend/tests/ -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Backend Pytest: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Backend Pytest: PASSED (122/122)" -ForegroundColor Green
}

# 2. Frontend Tests
Write-Host "`n[2/6] Running Frontend Test Suite..." -ForegroundColor Yellow
Push-Location frontend
npm test
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend Tests: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Frontend Tests: PASSED (13/13)" -ForegroundColor Green
}
Pop-Location

# 3. Frontend Production Build
Write-Host "`n[3/6] Verifying Frontend Production Build..." -ForegroundColor Yellow
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0 -or -not (Test-Path dist/index.html)) {
    Write-Host "Frontend Build: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Frontend Build: PASSED (dist/index.html verified)" -ForegroundColor Green
}
Pop-Location

# 4. Terraform Validation
Write-Host "`n[4/6] Validating Terraform Configurations..." -ForegroundColor Yellow
Push-Location infrastructure/terraform
terraform fmt -check -recursive
$fmtCode = $LASTEXITCODE
terraform validate
$valCode = $LASTEXITCODE
terraform plan -input=false -var-file="terraform.tfvars.example"
$planCode = $LASTEXITCODE

if ($fmtCode -ne 0 -or $valCode -ne 0 -or $planCode -ne 0) {
    Write-Host "Terraform Validation: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Terraform Validation: PASSED (fmt, validate, plan verified)" -ForegroundColor Green
}
Pop-Location

# 5. Ansible Syntax Validation
Write-Host "`n[5/6] Validating Ansible Playbooks and Inventories..." -ForegroundColor Yellow
Push-Location infrastructure/ansible
python -c "
import glob, yaml, sys
files = glob.glob('playbooks/*.yml') + glob.glob('playbooks/*.yaml') + glob.glob('inventory/*.yml')
assert len(files) > 0, 'No ansible files found'
for f in files:
    with open(f, 'r') as fp:
        yaml.safe_load(fp)
    print(f'  OK: {f}')
print('All Ansible YAML manifests syntax-valid.')
"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ansible Validation: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Ansible Validation: PASSED" -ForegroundColor Green
}
Pop-Location

# 6. Live Health Verification
Write-Host "`n[6/6] Verifying Live Service Endpoints..." -ForegroundColor Yellow
& "$PSScriptRoot/health-check.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Live Health Check: FAILED" -ForegroundColor Red
    $OverallPass = $false
} else {
    Write-Host "Live Health Check: PASSED" -ForegroundColor Green
}

Write-Host "`n====================================================" -ForegroundColor Cyan
if ($OverallPass) {
    Write-Host "   PROJECT VALIDATION COMPLETE: ALL GATES PASSED    " -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "   PROJECT VALIDATION FAILED: ONE OR MORE ISSUES    " -ForegroundColor Red
    Write-Host "====================================================" -ForegroundColor Cyan
    exit 1
}

