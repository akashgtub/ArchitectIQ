import jenkins.model.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import hudson.util.Secret

/**
 * Jenkins Groovy script to configure DevSecOps credentials:
 *   - snyk-token: Snyk API Token for dependency scanning
 *   - sonar-token: SonarQube User Token for code quality analysis
 *
 * Can be run via Jenkins Script Console (http://localhost:8081/script)
 * or via scripts/ci/configure-jenkins-credentials.ps1
 */
println "=========================================================="
println "   Configuring ArchitectIQ DevSecOps Jenkins Credentials   "
println "=========================================================="

def instance = Jenkins.get()
def domain = Domain.global()
def store = instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()

def upsertSecretText = { String id, String description, String secretValue ->
    if (!secretValue || secretValue.trim().isEmpty() || secretValue.startsWith("PLACEHOLDER_")) {
        println "[SKIP] Credential '${id}' was not provided or contains placeholder."
        return false
    }
    
    def existing = store.getCredentials(domain).find { it.id == id }
    if (existing != null) {
        store.removeCredentials(domain, existing)
        println "[UPDATE] Existing credential '${id}' removed for update."
    }
    
    def credential = new StringCredentialsImpl(
        CredentialsScope.GLOBAL,
        id,
        description,
        Secret.fromString(secretValue.trim())
    )
    store.addCredentials(domain, credential)
    println "[SUCCESS] Credential '${id}' successfully registered in Jenkins store."
    return true
}

// 1. Configure Snyk Token if present in environment or property
def snykToken = System.getenv("SNYK_TOKEN") ?: System.getProperty("snyk.token", "")
upsertSecretText("snyk-token", "Snyk API Token for DevSecOps Dependency Scanning", snykToken)

// 2. Configure SonarQube Token if present in environment or property
def sonarToken = System.getenv("SONAR_TOKEN") ?: System.getProperty("sonar.token", "")
upsertSecretText("sonar-token", "SonarQube User Token for DevSecOps Quality Gate", sonarToken)

// Summary of registered credentials
println "\n--- Current Credentials in System Store ---"
def creds = store.getCredentials(domain)
creds.each { c ->
    println "ID: ${c.id} | Type: ${c.class.simpleName} | Description: ${c.description}"
}
println "=========================================================="
