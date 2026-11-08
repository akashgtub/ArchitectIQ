<#
.SYNOPSIS
    Securely configures Snyk and SonarQube credentials in Jenkins Credentials Store.
.DESCRIPTION
    Injects SNYK_TOKEN and SONAR_TOKEN as Secret Text credentials into Jenkins
    via authenticated REST API without exposing tokens in logs or console output.
#>
[CmdletBinding()]
param(
    [string]$JenkinsUrl = "http://127.0.0.1:8081",
    [Parameter(Mandatory=$false)]
    [string]$SnykToken = "",
    [Parameter(Mandatory=$false)]
    [string]$SonarToken = "",
    [string]$SonarHostUrl = "http://architectiq-sonarqube:9000"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$tokenFile = Join-Path $RepoRoot "logs\jenkins\cicd-bot.token"

if (-not (Test-Path $tokenFile)) {
    Write-Host "[ERROR] cicd-bot token not found at $tokenFile." -ForegroundColor Red
    exit 1
}

$jenkinsUser = "cicd-bot"
$jenkinsToken = (Get-Content -Path $tokenFile).Trim()
$authHeader = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${jenkinsUser}:${jenkinsToken}"))

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   ArchitectIQ DevSecOps: Jenkins Credentials Injector    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Fetch Crumb
try {
    $crumbResp = Invoke-RestMethod -Uri "$JenkinsUrl/crumbIssuer/api/json" -Method Get -Headers @{ Authorization = $authHeader }
    $crumbHeader = $crumbResp.crumbRequestField
    $crumb = $crumbResp.crumb
} catch {
    Write-Host "[ERROR] Failed to acquire CSRF crumb from Jenkins ($($_.Exception.Message))." -ForegroundColor Red
    exit 1
}

# Groovy script to inject credentials
$groovyScript = @"
import jenkins.model.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import hudson.util.Secret

def domain = Domain.global()
def store = Jenkins.instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()

void upsert(store, domain, id, desc, secretVal) {
    if (!secretVal || secretVal.trim().isEmpty()) {
        println "[SKIP] Credential '\${id}' value was not provided."
        return
    }
    def existing = store.getCredentials(domain).find { it.id == id }
    if (existing != null) {
        store.removeCredentials(domain, existing)
    }
    def cred = new StringCredentialsImpl(
        CredentialsScope.GLOBAL,
        id,
        desc,
        Secret.fromString(secretVal.trim())
    )
    store.addCredentials(domain, cred)
    println "[SUCCESS] Credential '\${id}' successfully registered in Jenkins."
}

upsert(store, domain, 'snyk-token', 'Snyk API Token for DevSecOps Dependency Scanning', '$SnykToken')
upsert(store, domain, 'sonar-token', 'SonarQube User Token for DevSecOps Quality Gate', '$SonarToken')
"@

try {
    $headers = @{
        "Authorization" = $authHeader
        $crumbHeader    = $crumb
    }
    $resp = Invoke-RestMethod -Uri "$JenkinsUrl/scriptText" -Method Post -Headers $headers -Body @{ script = $groovyScript }
    Write-Host $resp -ForegroundColor Green
    Write-Host "`nCredential injection complete. Tokens are masked and secured in Jenkins." -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to execute credential configuration: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
