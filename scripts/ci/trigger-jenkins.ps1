<#
.SYNOPSIS
    Authoritative Jenkins REST API trigger and execution tracker for GitHub Actions self-hosted runner.
.DESCRIPTION
    - Authenticates via dedicated least-privileged service account (cicd-bot) and API token.
    - Handles Jenkins CSRF Crumb extraction and injection.
    - Single authoritative trigger mechanism via /job/{JobName}/buildWithParameters (no webhooks).
    - Prevents duplicate builds for the same triggering commit.
    - Captures queue item URL and polls until build number is assigned.
    - Progressively streams console log output from Jenkins.
    - Accurately evaluates build result (SUCCESS, FAILURE, ABORTED, UNSTABLE, TIMEOUT).
    - Downloads archived security reports via authenticated REST API.
    - Never prints tokens, secrets, or authorization headers.
#>
[CmdletBinding()]
param(
    [string]$JenkinsUrl = "http://127.0.0.1:8081",
    [string]$JobName = "ArchitectIQ-Pipeline",
    [ValidateSet("ADVISORY", "STRICT")]
    [string]$SecurityMode = "STRICT",
    [string]$CommitSha = "",
    [string]$Branch = "main",
    [string]$RunId = "",
    [int]$TimeoutSeconds = 1800
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   ArchitectIQ CI/CD Bridge: GitHub Actions -> Jenkins      " -ForegroundColor Cyan
Write-Host "         Authenticated REST API Trigger & Build Tracker     " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Jenkins Controller:  $JenkinsUrl" -ForegroundColor White
Write-Host "Pipeline Job:        $JobName" -ForegroundColor White
Write-Host "Security Mode:       $SecurityMode" -ForegroundColor Yellow
Write-Host "Triggering Branch:   $Branch" -ForegroundColor Gray
Write-Host "Triggering Commit:   $CommitSha" -ForegroundColor Gray
Write-Host "GitHub Run ID:       $RunId" -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor Gray

# ---------------------------------------------------------------------------
# 1. Resolve Credentials (cicd-bot Service Account + API Token)
# ---------------------------------------------------------------------------
Write-Host "`n[1/5] Resolving Jenkins API credentials..." -ForegroundColor Yellow

$jenkinsUser = if ($env:JENKINS_USER) { $env:JENKINS_USER.Trim() } else { "cicd-bot" }
$jenkinsToken = if ($env:JENKINS_API_TOKEN) { $env:JENKINS_API_TOKEN.Trim() } else { $null }

# Local fallback for self-hosted runner if environment variable is not passed
if (-not $jenkinsToken) {
    $tokenFile = Join-Path $RepoRoot "logs\jenkins\cicd-bot.token"
    if (Test-Path $tokenFile) {
        $jenkinsToken = (Get-Content -Path $tokenFile -ErrorAction SilentlyContinue).Trim()
    }
}

if (-not $jenkinsToken) {
    Write-Host "[ERROR] Missing Jenkins credentials." -ForegroundColor Red
    Write-Host "JENKINS_API_TOKEN is required to authenticate against the Jenkins REST API." -ForegroundColor Yellow
    Write-Host "Ensure the GitHub Actions secret JENKINS_API_TOKEN or local token file is configured." -ForegroundColor Yellow
    exit 1
}

Write-Host "Authenticated Service Account: $jenkinsUser" -ForegroundColor Green
Write-Host "API Token: [REDACTED - Length: $($jenkinsToken.Length) chars]" -ForegroundColor Gray

$authHeaderValue = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${jenkinsUser}:${jenkinsToken}"))
$authHeaders = @{
    "Authorization" = $authHeaderValue
}

# ---------------------------------------------------------------------------
# 2. Probe Jenkins Controller and Acquire CSRF Crumb
# ---------------------------------------------------------------------------
Write-Host "`n[2/5] Connecting to Jenkins controller and fetching CSRF crumb..." -ForegroundColor Yellow

# Health Probe
try {
    $loginResp = Invoke-WebRequest -Uri "$JenkinsUrl/login" -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($loginResp.StatusCode -ne 200 -and $loginResp.StatusCode -ne 403) {
        Write-Host "[ERROR] Jenkins controller returned unexpected HTTP status: $($loginResp.StatusCode)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Jenkins is unreachable at $JenkinsUrl ($($_.Exception.Message))." -ForegroundColor Red
    exit 1
}

# Crumb Acquisition
$crumbHeaderName = $null
$crumbValue = $null
$sessionCookie = $null

try {
    $crumbUrl = "$JenkinsUrl/crumbIssuer/api/json"
    $crumbRequest = [System.Net.HttpWebRequest]::Create($crumbUrl)
    $crumbRequest.Method = "GET"
    $crumbRequest.Headers.Add("Authorization", $authHeaderValue)
    $crumbRequest.Timeout = 10000
    $crumbRequest.CookieContainer = New-Object System.Net.CookieContainer

    $crumbResponse = $crumbRequest.GetResponse()
    $reader = New-Object System.IO.StreamReader($crumbResponse.GetResponseStream())
    $crumbJson = $reader.ReadToEnd() | ConvertFrom-Json
    $reader.Close()
    $crumbResponse.Close()

    $crumbHeaderName = $crumbJson.crumbRequestField
    $crumbValue = $crumbJson.crumb
    $sessionCookie = $crumbRequest.CookieContainer

    Write-Host "CSRF Protection: Active (Header: $crumbHeaderName)" -ForegroundColor Green
} catch [System.Net.WebException] {
    $resp = $_.Exception.Response
    if ($resp -and $resp.StatusCode -eq [System.Net.HttpStatusCode]::Unauthorized) {
        Write-Host "[ERROR] Jenkins authentication failed for user '$jenkinsUser' (HTTP 401 Unauthorized)." -ForegroundColor Red
        Write-Host "Verify the JENKINS_API_TOKEN is valid and not expired or revoked." -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "[INFO] CSRF CrumbIssuer not required or bypassed: $($_.Exception.Message)" -ForegroundColor Gray
    }
} catch {
    Write-Host "[INFO] CSRF Crumb handling: $($_.Exception.Message)" -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# 3. Duplicate Trigger Prevention Check
# ---------------------------------------------------------------------------
Write-Host "`n[3/5] Checking for duplicate or in-flight builds..." -ForegroundColor Yellow
$activeBuildUrl = $null
$activeBuildNum = $null

if ($CommitSha) {
    try {
        $jobInfoUrl = "$JenkinsUrl/job/$JobName/api/json?tree=builds[number,building,actions[parameters[name,value]]]"
        $jobReq = [System.Net.HttpWebRequest]::Create($jobInfoUrl)
        $jobReq.Method = "GET"
        $jobReq.Headers.Add("Authorization", $authHeaderValue)
        $jobReq.Timeout = 5000
        $jobResp = $jobReq.GetResponse()
        $jobData = (New-Object System.IO.StreamReader($jobResp.GetResponseStream())).ReadToEnd() | ConvertFrom-Json
        $jobResp.Close()

        foreach ($b in $jobData.builds) {
            if ($b.building) {
                foreach ($act in $b.actions) {
                    if ($act.parameters) {
                        $pSha = ($act.parameters | Where-Object { $_.name -eq "TRIGGERING_COMMIT_SHA" }).value
                        if ($pSha -and $pSha -eq $CommitSha) {
                            Write-Host "[INFO] In-flight build #$($b.number) already running for commit $CommitSha." -ForegroundColor Green
                            Write-Host "Attaching to existing build #$($b.number) to prevent duplicate execution." -ForegroundColor Cyan
                            $activeBuildNum = $b.number
                            $activeBuildUrl = "$JenkinsUrl/job/$JobName/$($b.number)/"
                            break
                        }
                    }
                }
            }
            if ($activeBuildNum) { break }
        }
    } catch {}
}

# ---------------------------------------------------------------------------
# 4. Trigger Build via Authenticated REST API (If Not Attached)
# ---------------------------------------------------------------------------
if (-not $activeBuildNum) {
    Write-Host "Dispatching authenticated build trigger..." -ForegroundColor Yellow
    
    $triggerEndpoint = "$JenkinsUrl/job/$JobName/buildWithParameters"
    $queryParams = @(
        "SECURITY_ENFORCEMENT_MODE=$([System.Uri]::EscapeDataString($SecurityMode))",
        "TRIGGERING_COMMIT_SHA=$([System.Uri]::EscapeDataString($CommitSha))",
        "TRIGGERING_BRANCH=$([System.Uri]::EscapeDataString($Branch))",
        "GITHUB_RUN_ID=$([System.Uri]::EscapeDataString($RunId))"
    ) -join "&"

    $fullTriggerUrl = "${triggerEndpoint}?${queryParams}"
    $triggerReq = [System.Net.HttpWebRequest]::Create($fullTriggerUrl)
    $triggerReq.Method = "POST"
    $triggerReq.Headers.Add("Authorization", $authHeaderValue)
    if ($crumbHeaderName -and $crumbValue) {
        $triggerReq.Headers.Add($crumbHeaderName, $crumbValue)
    }
    if ($sessionCookie) {
        $triggerReq.CookieContainer = $sessionCookie
    }
    $triggerReq.ContentLength = 0
    $triggerReq.Timeout = 15000

    $queueItemUrl = $null
    try {
        $triggerResp = $triggerReq.GetResponse()
        $statusCode = [int]$triggerResp.StatusCode
        $queueItemUrl = $triggerResp.Headers["Location"]
        $triggerResp.Close()

        if ($statusCode -eq 201 -and $queueItemUrl) {
            Write-Host "Build request accepted by Jenkins (HTTP 201 Created)." -ForegroundColor Green
            Write-Host "Queue Item URL: $queueItemUrl" -ForegroundColor Gray
        } else {
            Write-Host "[ERROR] Jenkins accepted request but returned unexpected status $statusCode" -ForegroundColor Red
            exit 1
        }
    } catch [System.Net.WebException] {
        $errResp = $_.Exception.Response
        if ($errResp) {
            $errCode = [int]$errResp.StatusCode
            if ($errCode -eq 401) {
                Write-Host "[ERROR] Authentication failed (HTTP 401 Unauthorized). Check user credentials." -ForegroundColor Red
            } elseif ($errCode -eq 403) {
                Write-Host "[ERROR] Authorization or CSRF check failed (HTTP 403 Forbidden)." -ForegroundColor Red
            } elseif ($errCode -eq 404) {
                Write-Host "[ERROR] Job '$JobName' not found on Jenkins controller (HTTP 404)." -ForegroundColor Red
            } else {
                Write-Host "[ERROR] Jenkins trigger failed: HTTP $errCode ($($_.Exception.Message))" -ForegroundColor Red
            }
        } else {
            Write-Host "[ERROR] Network error contacting Jenkins: $($_.Exception.Message)" -ForegroundColor Red
        }
        exit 1
    }

    # Poll Queue Item to Resolve Build Number
    Write-Host "Resolving build executor from queue..." -ForegroundColor Gray
    $queueTimeout = 60
    $qStart = [DateTime]::UtcNow

    while (-not $activeBuildNum) {
        Start-Sleep -Seconds 2
        try {
            $qReq = [System.Net.HttpWebRequest]::Create("${queueItemUrl}api/json")
            $qReq.Method = "GET"
            $qReq.Headers.Add("Authorization", $authHeaderValue)
            $qReq.Timeout = 5000
            $qResp = $qReq.GetResponse()
            $qData = (New-Object System.IO.StreamReader($qResp.GetResponseStream())).ReadToEnd() | ConvertFrom-Json
            $qResp.Close()

            if ($qData.cancelled) {
                Write-Host "[ERROR] Build was cancelled in Jenkins queue." -ForegroundColor Red
                exit 1
            }

            if ($qData.executable -and $qData.executable.number) {
                $activeBuildNum = $qData.executable.number
                $activeBuildUrl = $qData.executable.url
                break
            }

            if ($qData.why) {
                Write-Host "  Queue status: $($qData.why)" -ForegroundColor Gray
            }
        } catch {
            # Item might have transitioned out of queue
            break
        }

        if (([DateTime]::UtcNow - $qStart).TotalSeconds -gt $queueTimeout) {
            Write-Host "[ERROR] Queue polling timed out after $queueTimeout seconds." -ForegroundColor Red
            exit 1
        }
    }

    # Fallback resolution if queue item was removed immediately
    if (-not $activeBuildNum) {
        Start-Sleep -Seconds 3
        try {
            $lastBReq = [System.Net.HttpWebRequest]::Create("$JenkinsUrl/job/$JobName/lastBuild/api/json")
            $lastBReq.Method = "GET"
            $lastBReq.Headers.Add("Authorization", $authHeaderValue)
            $lastBResp = $lastBReq.GetResponse()
            $lastBData = (New-Object System.IO.StreamReader($lastBResp.GetResponseStream())).ReadToEnd() | ConvertFrom-Json
            $lastBResp.Close()
            $activeBuildNum = $lastBData.number
            $activeBuildUrl = $lastBData.url
        } catch {}
    }
}

if (-not $activeBuildNum) {
    Write-Host "[ERROR] Could not resolve assigned build number from Jenkins." -ForegroundColor Red
    exit 1
}

Write-Host "Assigned Build: #${activeBuildNum}" -ForegroundColor Green
Write-Host "Build URL:      $activeBuildUrl" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 5. Monitor Build Execution, Stream Logs, and Retrieve Artifacts
# ---------------------------------------------------------------------------
Write-Host "`n[4/5] Monitoring build execution and streaming console logs..." -ForegroundColor Yellow

$buildStart = [DateTime]::UtcNow
$isBuilding = $true
$logStart = 0
$finalResult = $null

while ($isBuilding) {
    Start-Sleep -Seconds 3

    # Progressive log streaming
    try {
        $logUrl = "${activeBuildUrl}logText/progressiveText?start=${logStart}"
        $logReq = [System.Net.HttpWebRequest]::Create($logUrl)
        $logReq.Method = "GET"
        $logReq.Headers.Add("Authorization", $authHeaderValue)
        $logReq.Timeout = 5000
        $logResp = $logReq.GetResponse()
        
        $newLogOffset = $logResp.Headers["X-Text-Size"]
        $hasMore = $logResp.Headers["X-More-Data"]
        
        $logText = (New-Object System.IO.StreamReader($logResp.GetResponseStream())).ReadToEnd()
        $logResp.Close()

        if ($logText) {
            [Console]::Write($logText)
        }

        if ($newLogOffset) {
            $logStart = [int64]$newLogOffset
        }
    } catch {}

    # Check build completion status
    try {
        $statusReq = [System.Net.HttpWebRequest]::Create("${activeBuildUrl}api/json")
        $statusReq.Method = "GET"
        $statusReq.Headers.Add("Authorization", $authHeaderValue)
        $statusReq.Timeout = 5000
        $statusResp = $statusReq.GetResponse()
        $statusData = (New-Object System.IO.StreamReader($statusResp.GetResponseStream())).ReadToEnd() | ConvertFrom-Json
        $statusResp.Close()

        if (-not $statusData.building) {
            $isBuilding = $false
            $finalResult = $statusData.result
            break
        }
    } catch {}

    if (([DateTime]::UtcNow - $buildStart).TotalSeconds -gt $TimeoutSeconds) {
        Write-Host "`n[ERROR] Pipeline execution exceeded timeout limit of $TimeoutSeconds seconds." -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "   Jenkins Pipeline Finished. Build Result: $finalResult    " -ForegroundColor $(if ($finalResult -eq "SUCCESS") { "Green" } else { "Red" })
Write-Host "============================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 6. Retrieve Archived Security Reports via Authenticated REST API
# ---------------------------------------------------------------------------
Write-Host "`n[5/5] Retrieving archived security reports from Jenkins build..." -ForegroundColor Yellow

$reportsTargetDir = Join-Path $RepoRoot "reports\security"
if (-not (Test-Path $reportsTargetDir)) {
    New-Item -ItemType Directory -Path $reportsTargetDir -Force | Out-Null
}

$artifactsToFetch = @(
    "reports/security/security-summary.md",
    "reports/security/security-summary.json"
)

foreach ($art in $artifactsToFetch) {
    $artFileName = Split-Path $art -Leaf
    $destinationFile = Join-Path $reportsTargetDir $artFileName
    $artifactDownloadUrl = "${activeBuildUrl}artifact/${art}"
    
    try {
        $artReq = [System.Net.HttpWebRequest]::Create($artifactDownloadUrl)
        $artReq.Method = "GET"
        $artReq.Headers.Add("Authorization", $authHeaderValue)
        $artReq.Timeout = 10000
        $artResp = $artReq.GetResponse()
        
        $artContent = (New-Object System.IO.StreamReader($artResp.GetResponseStream(), [System.Text.Encoding]::UTF8)).ReadToEnd()
        $artResp.Close()

        Set-Content -Path $destinationFile -Value $artContent -Encoding UTF8 -Force
        Write-Host "  Retrieved: $artFileName -> $destinationFile" -ForegroundColor Green
    } catch {
        Write-Host "  [WARNING] Could not retrieve artifact '$art' from Jenkins build: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# 7. Final Verdict Evaluation
# ---------------------------------------------------------------------------
switch ($finalResult) {
    "SUCCESS" {
        Write-Host "`n[VERDICT] Jenkins build #${activeBuildNum} PASSED successfully." -ForegroundColor Green
        exit 0
    }
    "UNSTABLE" {
        Write-Host "`n[VERDICT] Jenkins build #${activeBuildNum} marked as UNSTABLE (Quality gate warnings)." -ForegroundColor Yellow
        exit 1
    }
    "ABORTED" {
        Write-Host "`n[VERDICT] Jenkins build #${activeBuildNum} was ABORTED." -ForegroundColor Red
        exit 1
    }
    default {
        Write-Host "`n[VERDICT] Jenkins build #${activeBuildNum} FAILED with status '$finalResult'." -ForegroundColor Red
        exit 1
    }
}
