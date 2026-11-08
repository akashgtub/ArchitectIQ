<#
.SYNOPSIS
    Displays DevSecOps Security Framework summary across all 7 essential tools.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$SummaryJson = Join-Path $RepoRoot "reports\security\security-summary.json"
$SummaryMd = Join-Path $RepoRoot "reports\security\security-summary.md"
$VenvPy = Join-Path $RepoRoot "security\.venv\Scripts\python.exe"
$PyCmd = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
$RunnerPy = Join-Path $RepoRoot "security\framework\seven_gates_runner.py"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "      ArchitectIQ 7 Essential Security Gates Summary         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Ensure summary is freshly aggregated
& $PyCmd $RunnerPy --summary

if (Test-Path $SummaryJson) {
    try {
        $data = Get-Content $SummaryJson -Raw | ConvertFrom-Json
        Write-Host "`nOverall Verdict: $($data.overall_verdict)" -ForegroundColor $(if ($data.overall_verdict -eq "PASS") { "Green" } elseif ($data.overall_verdict -eq "BLOCKED") { "Yellow" } else { "Red" })
        Write-Host "Timestamp:       $($data.timestamp)"
        Write-Host "Passed Gates:    $($data.passed_gates) / $($data.total_gates)"
        Write-Host "Failed Gates:    $($data.failed_gates) / $($data.total_gates)"
        Write-Host "Blocked Gates:   $($data.blocked_gates) / $($data.total_gates)"

        Write-Host "`nGate Execution Breakdown:" -ForegroundColor Yellow
        $table = @()
        foreach ($k in ($data.gates.PSObject.Properties.Name | Sort-Object { [int]$_ })) {
            $g = $data.gates.$k
            $table += [PSCustomObject]@{
                Gate     = $k
                Name     = $g.name
                Tool     = $g.tool
                Status   = $g.status
                Verdict  = $g.verdict
                Findings = $g.findings
                Details  = if ($g.error_details) { $g.error_details } else { "Clean" }
            }
        }
        $table | Format-Table -AutoSize
    } catch {
        Get-Content $SummaryMd
    }
} else {
    Write-Host "[ERROR] Could not read summary report at $SummaryJson" -ForegroundColor Red
}

Write-Host "`nMarkdown report available at: $SummaryMd" -ForegroundColor Gray

