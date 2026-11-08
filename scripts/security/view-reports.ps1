<#
.SYNOPSIS
    Lists all DevSecOps gate reports with timestamps, verdicts, and findings count.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ReportsDir = Join-Path $RepoRoot "reports\security"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevSecOps Security Gate Reports          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $ReportsDir)) {
    Write-Host "[WARN] No reports directory found at $ReportsDir" -ForegroundColor Yellow
    exit 0
}

$files = Get-ChildItem -Path $ReportsDir -Filter "gate-*.json" | Sort-Object Name
if ($files.Count -eq 0) {
    Write-Host "No gate reports found. Run security gates first." -ForegroundColor Yellow
    exit 0
}

$table = @()
foreach ($f in $files) {
    try {
        $json = Get-Content $f.FullName -Raw | ConvertFrom-Json
        $table += [PSCustomObject]@{
            Gate        = if ($json.gate_number) { $json.gate_number } else { $json.gate_id }
            Tool        = $json.tool_name
            Status      = $json.execution_status
            Verdict     = $json.severity_verdict
            Findings    = if ($null -ne $json.findings_count) { $json.findings_count } else { 0 }
            Crit_High   = "$($json.critical_findings) / $($json.high_findings)"
            ReportFile  = $f.Name
        }
    } catch {
        $table += [PSCustomObject]@{
            Gate        = "?"
            Tool        = $f.Name
            Status      = "ERROR_PARSING"
            Verdict     = "UNKNOWN"
            Findings    = "-"
            Crit_High   = "- / -"
            ReportFile  = $f.Name
        }
    }
}

$table | Format-Table -AutoSize
Write-Host "Total Reports: $($files.Count) in $ReportsDir" -ForegroundColor Cyan
Write-Host "Summary JSON:  reports\security\security-summary.json" -ForegroundColor Gray
Write-Host "Summary MD:    reports\security\security-summary.md" -ForegroundColor Gray
