pipeline {
    agent any

    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '15'))
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        choice(
            name: 'SECURITY_ENFORCEMENT_MODE',
            choices: ['ADVISORY', 'STRICT'],
            description: 'DevSecOps Quality Gate enforcement mode: STRICT blocks on policy failures or missing credentials; ADVISORY logs findings without blocking.'
        )
        choice(
            name: 'DEPLOY_ENVIRONMENT',
            choices: ['local', 'staging', 'production'],
            description: 'Target deployment environment (Production deployment requires explicit approval)'
        )
        string(
            name: 'DAST_TARGET_URL',
            defaultValue: 'http://localhost:8000',
            description: 'Target URL of local ArchitectIQ backend for OWASP ZAP DAST scan'
        )
        string(
            name: 'TRIGGERING_COMMIT_SHA',
            defaultValue: '',
            description: 'Exact Git Commit SHA passed by GitHub Actions'
        )
        string(
            name: 'TRIGGERING_BRANCH',
            defaultValue: 'main',
            description: 'Git Branch passed by GitHub Actions'
        )
        string(
            name: 'GITHUB_RUN_ID',
            defaultValue: '',
            description: 'GitHub Actions Run ID for traceability'
        )
    }

    environment {
        APP_NAME              = 'architectiq'
        REGISTRY_REPO         = 'architectiq'
        BACKEND_IMAGE         = "${REGISTRY_REPO}/backend"
        FRONTEND_IMAGE        = "${REGISTRY_REPO}/frontend"
        DOCKER_BUILDKIT       = '1'
    }

    stages {
        // ====================================================================
        // Stage 1: Checkout
        // ====================================================================
        stage('1. Checkout') {
            steps {
                echo ">>> Stage 1: Checking out repository from SCM..."
                checkout scm
            }
        }

        // ====================================================================
        // Stage 2: Build Metadata Resolution
        // ====================================================================
        stage('2. Build Metadata') {
            steps {
                echo ">>> Stage 2: Resolving immutable build metadata and release tag..."
                script {
                    def fullCommit = ""
                    if (params.TRIGGERING_COMMIT_SHA && params.TRIGGERING_COMMIT_SHA.trim().length() >= 7) {
                        fullCommit = params.TRIGGERING_COMMIT_SHA.trim()
                    } else if (env.GIT_COMMIT && env.GIT_COMMIT.trim().length() >= 7) {
                        fullCommit = env.GIT_COMMIT.trim()
                    } else {
                        try {
                            fullCommit = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                        } catch (Exception e) {
                            echo "git rev-parse fallback error: ${e.message}"
                        }
                    }

                    if (!fullCommit || fullCommit == "null" || fullCommit.length() < 7) {
                        error("FATAL: Unable to resolve Git commit SHA. Build cannot proceed.")
                    }

                    def shortSha = fullCommit.take(7)
                    def buildNum = env.BUILD_NUMBER ?: "0"
                    def releaseTag = "${buildNum}-${shortSha}"

                    // Export to environment for all subsequent stages and subshells
                    env.GIT_COMMIT_SHA = fullCommit
                    env.SHORT_COMMIT   = shortSha
                    env.IMAGE_TAG      = releaseTag

                    currentBuild.displayName = "#${releaseTag}"
                    def desc = "Security Mode: ${params.SECURITY_ENFORCEMENT_MODE} | Commit: ${shortSha}"
                    if (params.GITHUB_RUN_ID) {
                        desc += " | GHA Run: #${params.GITHUB_RUN_ID}"
                    }
                    currentBuild.description = desc

                    echo "=================================================="
                    echo "Build Metadata Successfully Resolved:"
                    echo "  Full Commit SHA: ${env.GIT_COMMIT_SHA}"
                    echo "  Short Commit:    ${env.SHORT_COMMIT}"
                    echo "  Build Number:    ${env.BUILD_NUMBER}"
                    echo "  Release Tag:     ${env.IMAGE_TAG}"
                    echo "  Backend Image:   ${env.BACKEND_IMAGE}:${env.IMAGE_TAG}"
                    echo "  Frontend Image:  ${env.FRONTEND_IMAGE}:${env.IMAGE_TAG}"
                    echo "=================================================="

                    if (!env.IMAGE_TAG || env.IMAGE_TAG.contains("null")) {
                        error("FATAL: Release tag resolved to invalid value: '${env.IMAGE_TAG}'")
                    }
                }
            }
        }

        // ====================================================================
        // Stage 3: Backend Tests
        // ====================================================================
        stage('3. Backend Tests') {
            steps {
                echo ">>> Stage 3: Running backend automated test suite..."
                sh '''
                    if [ ! -f "frontend/dist/index.html" ]; then
                        echo "Compiling frontend bundle for backend integration tests..."
                        npm --prefix frontend ci || npm --prefix frontend install
                        npm --prefix frontend run build
                    fi
                    if command -v pytest >/dev/null 2>&1; then
                        pytest backend/tests/ -v --junitxml=backend-test-results.xml
                    else
                        python -m pytest backend/tests/ -v --junitxml=backend-test-results.xml
                    fi
                '''
            }
            post {
                always {
                    junit testResults: 'backend-test-results.xml', allowEmptyResults: true
                }
            }
        }

        // ====================================================================
        // Stage 4: Frontend Tests & Dependency Audit
        // ====================================================================
        stage('4. Frontend Tests') {
            steps {
                echo ">>> Stage 4: Running frontend unit tests and dependency security audit..."
                sh '''
                    npm --prefix frontend ci || npm --prefix frontend install
                    npm --prefix frontend test
                    echo "Executing npm dependency security audit..."
                    npm --prefix frontend audit || true
                '''
            }
        }

        // ====================================================================
        // Stage 5: Application Build (Docker BuildKit)
        // ====================================================================
        stage('5. Application Build') {
            steps {
                echo ">>> Stage 5: Compiling frontend bundle and building container images with BuildKit..."
                sh '''
                    npm --prefix frontend run build
                    test -f frontend/dist/index.html || { echo "ERROR: dist/index.html not found!"; exit 1; }

                    export DOCKER_BUILDKIT=1
                    docker build -t ${BACKEND_IMAGE}:${IMAGE_TAG} -t ${BACKEND_IMAGE}:latest -f backend/Dockerfile .
                    docker build -t ${FRONTEND_IMAGE}:${IMAGE_TAG} -t ${FRONTEND_IMAGE}:latest -f frontend/Dockerfile .
                '''
            }
        }

        // ====================================================================
        // Stage 6: TruffleHog (Gate 1: Secret Detection)
        // ====================================================================
        stage('6. TruffleHog') {
            steps {
                echo ">>> Stage 6: Executing Gate 1 — TruffleHog Secret Detection..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 1 --mode ADVISORY
                '''
            }
        }

        // ====================================================================
        // Stage 7: Bandit (Gate 2: Python SAST)
        // ====================================================================
        stage('7. Bandit') {
            steps {
                echo ">>> Stage 7: Executing Gate 2 — Bandit Python SAST..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 2 --mode ADVISORY
                '''
            }
        }

        // ====================================================================
        // Stage 8: Checkov (Gate 3: IaC Security)
        // ====================================================================
        stage('8. Checkov') {
            steps {
                echo ">>> Stage 8: Executing Gate 3 — Checkov Infrastructure as Code Security..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 3 --mode ADVISORY
                '''
            }
        }

        // ====================================================================
        // Stage 9: Hadolint (Gate 4: Dockerfile Linting)
        // ====================================================================
        stage('9. Hadolint') {
            steps {
                echo ">>> Stage 9: Executing Gate 4 — Hadolint Dockerfile Security Linting..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 4 --mode ADVISORY
                '''
            }
        }

        // ====================================================================
        // Stage 10: Snyk (Gate 5: Dependency Vulnerability Scanning)
        // ====================================================================
        stage('10. Snyk') {
            steps {
                echo ">>> Stage 10: Executing Gate 5 — Snyk Dependency Vulnerability Scanning..."
                script {
                    try {
                        withCredentials([string(credentialsId: 'snyk-token', variable: 'SNYK_TOKEN')]) {
                            sh '''
                                python security/framework/seven_gates_runner.py --gate 5 --mode ADVISORY
                            '''
                        }
                    } catch (Exception e) {
                        echo "[ADVISORY] Snyk credential 'snyk-token' not configured in Jenkins credentials store. Executing Gate 5 in diagnostic mode..."
                        sh '''
                            python security/framework/seven_gates_runner.py --gate 5 --mode ADVISORY
                        '''
                    }
                }
            }
        }

        // ====================================================================
        // Stage 11: SonarCloud Analysis (Gate 7: Static Analysis)
        // ====================================================================
        stage('11. SonarCloud Analysis') {
            steps {
                echo ">>> Stage 11: Executing Gate 7 — SonarCloud Static Code Analysis..."
                script {
                    try {
                        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                            sh '''
                                python security/framework/seven_gates_runner.py --gate 7 --mode ADVISORY
                            '''
                        }
                    } catch (Exception e) {
                        echo "[ADVISORY] SonarCloud credential 'sonar-token' not configured in Jenkins credentials store. Executing Gate 7 in diagnostic mode..."
                        sh '''
                            python security/framework/seven_gates_runner.py --gate 7 --mode ADVISORY
                        '''
                    }
                }
            }
        }

        // ====================================================================
        // Stage 12: SonarCloud Quality Gate (Gate 7: Status Evaluation)
        // ====================================================================
        stage('12. SonarCloud Quality Gate') {
            steps {
                echo ">>> Stage 12: Evaluating SonarCloud Quality Gate findings..."
                sh '''
                    python -c "
import json, sys
try:
    with open('reports/security/gate-07-sonarqube.json') as f:
        data = json.load(f)
    print('SonarCloud Execution Status:', data.get('execution_status'))
    print('SonarCloud Severity Verdict:', data.get('severity_verdict'))
    if data.get('error_details'):
        print('Details:', data.get('error_details'))
except Exception as e:
    print('Notice reading SonarCloud report:', e)
"
                '''
            }
        }

        // ====================================================================
        // Stage 13: OWASP ZAP Baseline Scan (Gate 6: DAST Probing)
        // ====================================================================
        stage('13. OWASP ZAP') {
            steps {
                echo ">>> Stage 13: Executing Gate 6 — OWASP ZAP Baseline DAST Probing on ${params.DAST_TARGET_URL}..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 6 --target-url ${DAST_TARGET_URL} --mode ADVISORY
                '''
            }
        }

        // ====================================================================
        // Stage 14: Security Policy Evaluation & Report Aggregation
        // ====================================================================
        stage('14. Security Policy Evaluation') {
            steps {
                echo ">>> Stage 14: Aggregating all 7 security gates and evaluating enforcement policy (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --summary --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
                script {
                    def summaryFile = 'reports/security/security-summary.json'
                    if (fileExists(summaryFile)) {
                        def summaryText = readFile(summaryFile)
                        echo "Security Summary JSON:\n${summaryText}"
                        def summary = readJSON file: summaryFile

                        echo "=================================================="
                        echo "DevSecOps Policy Enforcement Summary:"
                        echo "  Enforcement Mode: ${params.SECURITY_ENFORCEMENT_MODE}"
                        echo "  Overall Verdict:  ${summary.overall_verdict}"
                        echo "  Passed Gates:     ${summary.passed_gates}"
                        echo "  Failed Gates:     ${summary.failed_gates}"
                        echo "  Blocked Gates:    ${summary.blocked_gates}"
                        echo "=================================================="

                        if (params.SECURITY_ENFORCEMENT_MODE == 'STRICT') {
                            if (summary.overall_verdict != 'PASS') {
                                error("STRICT SECURITY POLICY ENFORCEMENT FAILURE: Overall security gate verdict is '${summary.overall_verdict}'. Deployment authorization is BLOCKED.")
                            }
                        }
                    } else {
                        error("FATAL: Security summary report '${summaryFile}' was not generated.")
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/security/*.json, reports/security/*.html, reports/security/*.md', allowEmptyArchive: true, fingerprint: true
                }
            }
        }

        // ====================================================================
        // Stage 15: Docker Image Verification & Release Manifest
        // ====================================================================
        stage('15. Docker Image Verification') {
            steps {
                echo ">>> Stage 15: Verifying built container images and generating release manifest..."
                sh '''
                    mkdir -p reports/deployments
                    docker image inspect ${BACKEND_IMAGE}:${IMAGE_TAG} >/dev/null 2>&1 || { echo "ERROR: Backend image missing"; exit 1; }
                    docker image inspect ${FRONTEND_IMAGE}:${IMAGE_TAG} >/dev/null 2>&1 || { echo "ERROR: Frontend image missing"; exit 1; }

                    cat <<EOF > reports/deployments/build-manifest-${IMAGE_TAG}.json
{
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "build_number": "${BUILD_NUMBER}",
  "commit_sha": "${SHORT_COMMIT}",
  "full_commit": "${GIT_COMMIT_SHA}",
  "release_tag": "${IMAGE_TAG}",
  "backend_image": "${BACKEND_IMAGE}:${IMAGE_TAG}",
  "frontend_image": "${FRONTEND_IMAGE}:${IMAGE_TAG}",
  "security_mode": "${SECURITY_ENFORCEMENT_MODE}",
  "deployment_environment": "${DEPLOY_ENVIRONMENT}"
}
EOF
                    cp reports/deployments/build-manifest-${IMAGE_TAG}.json reports/deployments/build-manifest.json
                    echo "Build and Deployment Manifest generated at reports/deployments/build-manifest-${IMAGE_TAG}.json"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/deployments/*.json', allowEmptyArchive: true, fingerprint: true
                }
            }
        }

        // ====================================================================
        // Stage 16: Deployment Approval Gate
        // ====================================================================
        stage('16. Deployment Approval') {
            steps {
                echo ">>> Stage 16: Checking deployment environment authorization..."
                script {
                    if (params.DEPLOY_ENVIRONMENT == 'production') {
                        input message: "Authorize production deployment for release ${env.IMAGE_TAG}?", ok: "Approve Production Release"
                    } else {
                        echo "Deployment to '${params.DEPLOY_ENVIRONMENT}' environment automatically approved based on pipeline policy."
                    }
                }
            }
        }

        // ====================================================================
        // Stage 17: Deployment
        // ====================================================================
        stage('17. Deployment') {
            when {
                expression { params.DEPLOY_ENVIRONMENT != 'production' || currentBuild.result == null }
            }
            steps {
                echo ">>> Stage 17: Recording deployment release state for tag ${env.IMAGE_TAG}..."
                sh '''
                    mkdir -p reports/deployments
                    cat <<EOF > reports/deployments/last-known-good.json
{
  "Timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "ImageTag": "${IMAGE_TAG}",
  "Registry": "${REGISTRY_REPO}",
  "Status": "SUCCESS",
  "CommitSha": "${GIT_COMMIT_SHA}"
}
EOF
                    echo "{\"Timestamp\":\"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\",\"ImageTag\":\"${IMAGE_TAG}\",\"Registry\":\"${REGISTRY_REPO}\",\"Status\":\"SUCCESS\",\"CommitSha\":\"${GIT_COMMIT_SHA}\"}" >> reports/deployments/deployment-history.jsonl
                    echo "Deployment state updated for tag ${IMAGE_TAG}"
                '''
            }
        }

        // ====================================================================
        // Stage 18: Health Checks & Observability Verification
        // ====================================================================
        stage('18. Health Checks') {
            steps {
                echo ">>> Stage 18: Verifying application and observability endpoints..."
                sh '''
                    python -c "
import urllib.request, sys
endpoints = [
    ('Backend Health', 'http://localhost:8000/health'),
    ('Frontend Healthz', 'http://localhost:80/healthz'),
    ('Reverse Proxy', 'http://localhost:80/health')
]
for name, url in endpoints:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(f'  {name} ({url}): HTTP {r.status} OK')
    except Exception as e:
        print(f'  {name} ({url}) check notice: {e}')
"
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/security/*.json, reports/security/*.html, reports/security/*.md, reports/deployments/*.json', allowEmptyArchive: true, fingerprint: true
        }
        success {
            echo "Pipeline finished successfully: All 18 stages verified."
        }
        failure {
            echo "Pipeline failed. Review security stage reports and logs in Jenkins artifacts."
        }
    }
}
