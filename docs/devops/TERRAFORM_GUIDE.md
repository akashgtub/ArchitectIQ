# ArchitectIQ — Terraform Infrastructure as Code Guide

## 1. Overview

ArchitectIQ employs Terraform to manage cluster-level resources and configuration primitives in a local-first Kubernetes environment. This ensures reproducible environments across developer machines, CI test runners, and staging clusters.

---

## 2. Directory Architecture

```text
infrastructure/terraform/
├── versions.tf                   # Declares >= 1.5.0 and provider versions
├── providers.tf                  # Local Kubernetes & Helm provider configuration
├── main.tf                       # Module orchestration
├── variables.tf                  # Global input parameters
├── outputs.tf                    # Deployment outputs
├── terraform.tfvars.example      # Example variable values
├── environments/                 # Environment layers
│   ├── local/                    # Local dev cluster overrides
│   └── production/               # Production namespace & replica specs
└── modules/                      # Reusable modular components
    ├── kubernetes_namespace/     # Declarative namespace provisioning
    └── app_config/               # Application ConfigMap management
```

---

## 3. Providers & Local Cluster Configuration

Terraform communicates with the local Kubernetes cluster via the standard `~/.kube/config` context:

```hcl
provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}
```

Supported local engines include:
- Docker Desktop Kubernetes (`docker-desktop`)
- Minikube (`minikube`)
- Kind (`kind-kind`)

---

## 4. Module Specifications

### `kubernetes_namespace` Module
- Provisions the isolated `architectiq` namespace.
- Attaches standard Kubernetes labels (`app.kubernetes.io/name`, `app.kubernetes.io/part-of`, `environment`).

### `app_config` Module
- Declaratively provisions the `architectiq-config` ConfigMap containing environment variables (`ENVIRONMENT`, `PORT`, `AI_PROVIDER`, `USE_MOCK_SIMULATOR`).
- Keeps non-sensitive configurations under version control.

---

## 5. Execution Workflow (Documentation Reference Only)

```bash
cd infrastructure/terraform
terraform init

terraform plan -var-file=terraform.tfvars.example

terraform apply -var-file=terraform.tfvars.example -auto-approve

terraform output
```

