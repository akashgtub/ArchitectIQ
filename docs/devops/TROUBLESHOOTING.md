# ArchitectIQ — DevOps Troubleshooting Guide

## 1. Quick Diagnostic Decision Tree

```text
Issue Detected
   │
   ├─► Jenkins Build Fails at Security Gate (Stage 9 or 10)
   │     └─► Check SECURITY_ENFORCEMENT_MODE. If STRICT, missing snyk-token or sonar-token blocks the build.
   │         Set mode to ADVISORY for non-blocking execution, or add credential in Jenkins.
   │
   ├─► Docker Compose Deployment Fails / Auto-Rollback Triggered
   │     └─► scripts/deploy/deploy-docker.ps1 probed :8000, :80, or proxy and received non-200.
   │         Check container logs: `docker logs architectiq-backend` or `docker logs architectiq-frontend`.
   │
   ├─► GitHub Actions CI/CD Bridge Fails with HTTP 403 / Crumb Error
   │     └─► Verify cicd-bot API token in logs/jenkins/cicd-bot.token or GitHub Secrets.
   │         Confirm CSRF crumb issuer is reachable at http://localhost:8081/crumbIssuer/api/json.
   │
   ├─► Prometheus Active Target Shows 'DOWN'
   │     └─► Query http://localhost:9090/api/v1/targets.
   │         Ensure target container is attached to architectiq-network and port is reachable.
   │
   └─► Terraform Validate Hangs on Windows
         └─► AWS provider attempts connection to link-local metadata IP 169.254.169.254.
             Ensure skip_metadata_api_check = true and skip_credentials_validation = true in providers.tf.
```

---

## 2. Common Scenarios & Resolutions

### Scenario 1: Security Gate Fails Pipeline with `BLOCKED` or `FAIL`
- **Symptom**: Jenkins build halts at Stage 11 (Security Policy Evaluation) with exit code 1.
- **Root Cause**: The pipeline was triggered in `STRICT` mode, and one of the 5 mandatory gates (TruffleHog, Bandit, Checkov, Hadolint, OWASP ZAP) reported critical/high findings, missing scanner, or unreachable target.
- **Resolution**:
  - Review archived gate reports in `reports/security/gate-0X-*.json`.
  - Fix detected security issues in code, Dockerfiles, or Terraform.
  - To run in diagnostic mode for testing: Pass parameter `SECURITY_ENFORCEMENT_MODE=ADVISORY` when triggering the build.

---

### Scenario 2: Post-Deployment Health Check Failure & Automatic Rollback
- **Symptom**: Deployment script reports `Health verification failed! Application containers did not respond within 60s` and automatically rolls back.
- **Root Cause**: The backend or frontend container crashed on startup or did not listen on the expected port (`8000` for backend, `80` for frontend).
- **Resolution**:
  - Check container logs immediately:
    ```powershell
    docker logs --tail 50 architectiq-backend
    docker logs --tail 50 architectiq-frontend
    ```
  - Verify that `reports/deployments/last-known-good.json` successfully restored the prior stable tag.
  - Fix any syntax or configuration errors in `backend/` or `frontend/`, rebuild images, and redeploy.

---

### Scenario 3: Jenkins API CSRF Crumb Error (403 Forbidden)
- **Symptom**: `scripts/ci/trigger-jenkins.ps1` fails with HTTP 403 when requesting `/crumbIssuer/api/json` or triggering `/buildWithParameters`.
- **Root Cause**: Outdated or invalid API token for service account `cicd-bot`.
- **Resolution**:
  - Confirm token in `logs/jenkins/cicd-bot.token`.
  - In Jenkins UI (`http://localhost:8081`), log in as admin, navigate to user `cicd-bot`, generate a fresh API token, and update the file and GitHub Secrets.

---

### Scenario 4: Terraform Hangs During Provider Initialization
- **Symptom**: `terraform validate` or `terraform plan` hangs indefinitely without CPU activity.
- **Root Cause**: The AWS provider tries to connect to AWS EC2 metadata IP `169.254.169.254`. On non-AWS Windows hosts, Windows waits for TCP socket timeout.
- **Resolution**:
  - In `infrastructure/terraform/environments/aws/providers.tf`, configure:
    ```hcl
    provider "aws" {
      region                      = var.aws_region
      skip_credentials_validation = true
      skip_requesting_account_id  = true
      skip_metadata_api_check     = true
    }
    ```
  - Set `$env:AWS_EC2_METADATA_DISABLED="true"`.
