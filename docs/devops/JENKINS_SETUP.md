# ArchitectIQ — Jenkins Controller & Agent Setup Guide

## 1. Overview

This guide details the setup and configuration of the Jenkins CI/CD automation server required to execute the ArchitectIQ Declarative Pipeline (`Jenkinsfile`).

---

## 2. Recommended Jenkins Controller Setup

Jenkins can be deployed via Docker or directly on a Linux host.

### Controller Requirements
- **Memory**: Minimum 4GB RAM (8GB recommended for concurrent builds).
- **Disk**: 50GB SSD storage for build history and workspace caches.
- **Java Runtime**: OpenJDK 17 or 21.

### Example Controller Launch via Docker (Reference Only)
```bash
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts-jdk17
```

---

## 3. Required Jenkins Plugins

Ensure the following plugins are installed via **Manage Jenkins > Plugins > Available Plugins**:

1. **Pipeline** (workflow-aggregator)
2. **Git Plugin** & **GitHub Integration Plugin**
3. **Credentials Binding Plugin**
4. **Docker Pipeline Plugin**
5. **Kubernetes CLI Plugin**
6. **JUnit Plugin** (for publishing Pytest test reports)
7. **AnsiColor Plugin** (for colored terminal logs)

---

## 4. Required Jenkins Credentials

Navigate to **Manage Jenkins > Credentials > System > Global credentials** and register:

| Credential ID | Kind | Description |
| :--- | :--- | :--- |
| `docker-registry-credentials` | Username with password | Docker Hub or private container registry credentials. |
| `kubeconfig-credentials` | Secret file | Kubeconfig file granting deployment permissions to Kubernetes. |
| `github-webhook-token` | Secret text | GitHub Personal Access Token for commit status updates. |

---

## 5. GitHub Webhook Configuration

To enable automated pipeline triggers upon source code push:

1. Open your GitHub repository: `https://github.com/<owner>/ArchitectIQ`.
2. Go to **Settings > Webhooks > Add webhook**.
3. **Payload URL**: `http://<your-jenkins-host>:8080/github-webhook/`
4. **Content type**: `application/json`
5. **Secret**: Optional HMAC secret token.
6. **Events**: Select **Just the push event** (or **Pull requests** as well).
7. Save the webhook.

---

## 6. Pipeline Job Creation

1. In Jenkins, click **New Item**.
2. Select **Pipeline** or **Multibranch Pipeline**.
3. Name the item `ArchitectIQ-Pipeline`.
4. In the **Pipeline** configuration tab:
   - **Definition**: `Pipeline script from SCM`
   - **SCM**: `Git`
   - **Repository URL**: `https://github.com/akashgtub/ArchitectIQ.git`
   - **Script Path**: `Jenkinsfile`
5. Click **Save** and trigger an initial build via **Build with Parameters**.

