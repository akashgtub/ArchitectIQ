import jenkins.model.*
import hudson.security.*
import jenkins.security.*

println(">>> Executing CI/CD Service Account Groovy Init Script...")
def instance = Jenkins.get()
def realm = instance.getSecurityRealm()

def username = "cicd-bot"
def user = instance.getUser(username)
if (user == null) {
    println(">>> Creating user: ${username}")
    user = realm.createAccount(username, "CicdBotSecret2026!")
    user.setFullName("GitHub Actions CI/CD Service Account")
    user.setDescription("Dedicated service account for GitHub Actions self-hosted runner integration")
    user.save()
}

// Ensure user has API Token
def apiTokenProperty = user.getProperty(ApiTokenProperty.class)
if (apiTokenProperty == null) {
    apiTokenProperty = new ApiTokenProperty()
    user.addProperty(apiTokenProperty)
}

def tokenStore = apiTokenProperty.getTokenStore()
def existingToken = tokenStore.tokenList.find { it.name == "github-actions-token" }

def tokenFile = new File("/var/jenkins_home/cicd-bot-token.txt")
if (existingToken == null || !tokenFile.exists() || tokenFile.length() == 0) {
    println(">>> Generating new API Token for ${username}")
    def result = tokenStore.generateNewToken("github-actions-token")
    user.save()
    tokenFile.text = result.plainValue.trim()
    println(">>> Token generated and stored in /var/jenkins_home/cicd-bot-token.txt")
} else {
    println(">>> API token already exists for ${username}")
}

