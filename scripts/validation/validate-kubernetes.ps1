<#
.SYNOPSIS
    Validates Kubernetes manifests using client dry-run without modifying cluster state.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$K8sDir = Join-Path $RepoRoot "infrastructure\kubernetes"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ Kubernetes Manifest Validation           " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n[1/1] Validating Kustomize and Kubernetes manifests (dry-run=client)..." -ForegroundColor Yellow
$out = kubectl apply --dry-run=client -k $K8sDir 2>&1
$exitCode = $LASTEXITCODE

Write-Host $out

Write-Host "============================================================" -ForegroundColor Cyan
if ($exitCode -eq 0) {
    Write-Host "Kubernetes Validation: ALL MANIFESTS VALID (PASS)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Kubernetes Validation: ERRORS DETECTED (FAIL)" -ForegroundColor Red
    exit 1
}

