<#
.SYNOPSIS
    Reports status of all DevOps Infrastructure components:
    Docker, Monitoring, Jenkins, Kubernetes cluster, Terraform, and Ansible.
#>
$ErrorActionPreference = "Continue"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       ArchitectIQ DevOps Infrastructure Status             " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Docker Engine
$dockerStatus = "DOWN"
$dockerDetail = "Daemon unreachable"
try {
    $info = docker info --format '{{.ServerVersion}} (Containers: {{.ContainersRunning}}/{{.Containers}})' 2>$null
    if ($LASTEXITCODE -eq 0 -and $info) {
        $dockerStatus = "HEALTHY"
        $dockerDetail = "v$info"
    }
} catch {}

# 2. Monitoring (Prometheus & Grafana)
$promStatus = "DOWN"
try {
    $web = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200) { $promStatus = "HEALTHY" }
} catch {}

$grafanaStatus = "DOWN"
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:3001/api/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($resp.database -eq "ok") { $grafanaStatus = "HEALTHY" }
} catch {}

# 3. Jenkins CI/CD
$jenkinsStatus = "DOWN"
try {
    $web = Invoke-WebRequest -Uri "http://127.0.0.1:8081/login" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($web.StatusCode -eq 200 -or $web.StatusCode -eq 403) { $jenkinsStatus = "HEALTHY" }
} catch {
    if ($_.Exception.Response -and ($_.Exception.Response.StatusCode.value__ -eq 403 -or $_.Exception.Response.StatusCode.value__ -eq 200)) {
        $jenkinsStatus = "HEALTHY"
    }
}

# 4. Kubernetes (Docker Desktop)
$k8sStatus = "OFFLINE"
$k8sDetail = "Cluster unreachable"
try {
    $nodes = kubectl get nodes --request-timeout=3s -o jsonpath='{.items[*].metadata.name}' 2>$null
    if ($LASTEXITCODE -eq 0 -and $nodes) {
        $k8sStatus = "READY"
        $k8sDetail = "Node: $nodes"
    }
} catch {}

# 5. Terraform Configuration
$tfStatus = "CONFIGURED"
$tfDir = Join-Path $RepoRoot "infrastructure\terraform\environments\local"
if (-not (Test-Path $tfDir)) { $tfStatus = "MISSING" }

# 6. Ansible Playbooks
$ansibleStatus = "CONFIGURED"
$ansibleDir = Join-Path $RepoRoot "infrastructure\ansible"
if (-not (Test-Path $ansibleDir)) { $ansibleStatus = "MISSING" }

# Output Summary Table
$results = @(
    [PSCustomObject]@{ Component = "Docker Engine"; Status = $dockerStatus; Detail = $dockerDetail }
    [PSCustomObject]@{ Component = "Prometheus (Port 9090)"; Status = $promStatus; Detail = "Time-series monitoring" }
    [PSCustomObject]@{ Component = "Grafana (Port 3001)"; Status = $grafanaStatus; Detail = "Dashboards & alerts" }
    [PSCustomObject]@{ Component = "Jenkins CI/CD (Port 8081)"; Status = $jenkinsStatus; Detail = "20-stage pipeline controller" }
    [PSCustomObject]@{ Component = "Kubernetes Engine"; Status = $k8sStatus; Detail = $k8sDetail }
    [PSCustomObject]@{ Component = "Terraform IaC"; Status = $tfStatus; Detail = "Environments: local, aws, prod" }
    [PSCustomObject]@{ Component = "Ansible Playbooks"; Status = $ansibleStatus; Detail = "Roles & playbooks ready" }
)

Write-Host "`nDevOps Infrastructure Components:" -ForegroundColor Yellow
$results | Format-Table -AutoSize

