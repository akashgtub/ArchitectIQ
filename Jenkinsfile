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
            description: 'DevSecOps Quality Gate enforcement mode: STRICT blocks on policy failures/missing credentials; ADVISORY logs findings without blocking.'
        )
        choice(
            name: 'DEPLOY_ENVIRONMENT',
            choices: ['local', 'staging', 'production'],
            description: 'Target deployment environment (Production deployment disabled by default)'
        )
        string(
            name: 'DAST_TARGET_URL',
            defaultValue: 'http://localhost:8000',
            description: 'Target URL of local ArchitectIQ environment for OWASP ZAP DAST scan'
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
        
        SHORT_COMMIT          = ''
        IMAGE_TAG             = ''
    }

    stages {
        // ====================================================================
        // Stage 1: Checkout
        // ====================================================================
        stage('1. Checkout') {
            steps {
                echo ">>> Stage 1: Checkout repository and determine build metadata..."
                checkout scm
                script {
                    SHORT_COMMIT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                    IMAGE_TAG = "${BUILD_NUMBER}-${SHORT_COMMIT}"
                    currentBuild.displayName = "#${BUILD_NUMBER}-${SHORT_COMMIT}"
                    def desc = "Security Mode: ${params.SECURITY_ENFORCEMENT_MODE} | Commit: ${SHORT_COMMIT}"
                    if (params.GITHUB_RUN_ID) {
                        desc += " | GHA Run: #${params.GITHUB_RUN_ID}"
                    }
                    currentBuild.description = desc
                    echo "Build Tag: ${IMAGE_TAG}"
                    if (params.GITHUB_RUN_ID) {
                        echo "Triggered by GitHub Actions Run ID: ${params.GITHUB_RUN_ID} (Branch: ${params.TRIGGERING_BRANCH}, Commit: ${params.TRIGGERING_COMMIT_SHA})"
                    }
                }
            }
        }

        // ====================================================================
        // Stage 2: Backend Tests
        // ====================================================================
        stage('2. Backend Tests') {
            steps {
                echo ">>> Stage 2: Running backend automated test suite..."
                sh '''
                    if [ ! -f "frontend/dist/index.html" ]; then
                        echo "Compiling frontend bundle for integration tests..."
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
        // Stage 3: Frontend Tests
        // ====================================================================
        stage('3. Frontend Tests') {
            steps {
                echo ">>> Stage 3: Running frontend test suite..."
                sh '''
                    npm --prefix frontend ci || npm --prefix frontend install
                    npm --prefix frontend test
                '''
            }
        }

        // ====================================================================
        // Stage 4: Application Build
        // ====================================================================
        stage('4. Application Build') {
            steps {
                echo ">>> Stage 4: Compiling frontend bundle and building container images..."
                sh '''
                    npm --prefix frontend run build
                    test -f frontend/dist/index.html || { echo "ERROR: dist/index.html not found!"; exit 1; }
                    docker build -t ${BACKEND_IMAGE}:${IMAGE_TAG} -t ${BACKEND_IMAGE}:latest -f backend/Dockerfile .
                    docker build -t ${FRONTEND_IMAGE}:${IMAGE_TAG} -t ${FRONTEND_IMAGE}:latest -f frontend/Dockerfile .
                '''
            }
        }

        // ====================================================================
        // Stage 5: TruffleHog (Gate 1: Secret Detection)
        // ====================================================================
        stage('5. TruffleHog') {
            steps {
                echo ">>> Stage 5: Executing Gate 1 — TruffleHog Secret Detection (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 1 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 6: Bandit (Gate 2: Python SAST)
        // ====================================================================
        stage('6. Bandit') {
            steps {
                echo ">>> Stage 6: Executing Gate 2 — Bandit Python SAST (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 2 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 7: Checkov (Gate 3: IaC Security)
        // ====================================================================
        stage('7. Checkov') {
            steps {
                echo ">>> Stage 7: Executing Gate 3 — Checkov Infrastructure as Code Security (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 3 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 8: Hadolint (Gate 4: Dockerfile Linting)
        // ====================================================================
        stage('8. Hadolint') {
            steps {
                echo ">>> Stage 8: Executing Gate 4 — Hadolint Dockerfile Security Linting (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 4 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 9: Snyk (Gate 5: Dependency Scanning)
        // ====================================================================
        stage('9. Snyk') {
            steps {
                echo ">>> Stage 9: Executing Gate 5 — Snyk Dependency Vulnerability Scanning (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 5 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 10: SonarQube Analysis (Gate 7: Static Analysis)
        // ====================================================================
        stage('10. SonarQube Analysis') {
            steps {
                echo ">>> Stage 10: Executing Gate 7 — SonarQube Code Quality & Security Analysis (${params.SECURITY_ENFORCEMENT_MODE})..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 7 --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 11: SonarQube Quality Gate (Gate 7: Quality Gate Check)
        // ====================================================================
        stage('11. SonarQube Quality Gate') {
            steps {
                echo ">>> Stage 11: Evaluating SonarQube Quality Gate status..."
                sh '''
                    python -c "
import json, sys
try:
    with open('reports/security/gate-07-sonarqube.json') as f:
        data = json.load(f)
    print('SonarQube Verdict:', data.get('severity_verdict'))
    print('Execution Status:', data.get('execution_status'))
    if '${SECURITY_ENFORCEMENT_MODE}' == 'STRICT' and data.get('severity_verdict') in ['FAIL', 'BLOCKED']:
        sys.exit(1)
except Exception as e:
    print('Error reading SonarQube report:', e)
    if '${SECURITY_ENFORCEMENT_MODE}' == 'STRICT':
        sys.exit(1)
"
                '''
            }
        }

        // ====================================================================
        // Stage 12: OWASP ZAP Baseline Scan (Gate 6: DAST)
        // ====================================================================
        stage('12. OWASP ZAP Baseline Scan') {
            steps {
                echo ">>> Stage 12: Executing Gate 6 — OWASP ZAP Baseline DAST Probing on ${params.DAST_TARGET_URL}..."
                sh '''
                    python security/framework/seven_gates_runner.py --gate 6 --target-url ${DAST_TARGET_URL} --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
            }
        }

        // ====================================================================
        // Stage 13: Security Report Aggregation
        // ====================================================================
        stage('13. Security Report Aggregation') {
            steps {
                echo ">>> Stage 13: Aggregating all security gate reports and publishing summary..."
                sh '''
                    python security/framework/seven_gates_runner.py --summary --mode ${SECURITY_ENFORCEMENT_MODE}
                '''
                script {
                    def summaryFile = 'reports/security/security-summary.json'
                    if (fileExists(summaryFile)) {
                        def summaryText = readFile(summaryFile)
                        echo "Security Summary JSON:\n${summaryText}"
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/security/*.json, reports/security/*.html, reports/security/*.md', allowEmptyArchive: true, fingerprint: true
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/security/*.json, reports/security/*.html, reports/security/*.md', allowEmptyArchive: true, fingerprint: true
        }
        success {
            echo "Pipeline finished successfully: All 13 stages completed."
        }
        failure {
            echo "Pipeline failed. Review security stage reports and logs in Jenkins artifacts."
        }
    }
}
