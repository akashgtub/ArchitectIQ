# ArchitectIQ — Terraform Infrastructure as Code (IaC)

This directory defines the local-first Kubernetes infrastructure for the **ArchitectIQ** platform using Terraform.

## Directory Structure

```text
infrastructure/terraform/
├── versions.tf                   # Terraform version & provider constraints
├── providers.tf                  # Kubernetes and Helm provider definitions
├── main.tf                       # Root orchestration calling child modules
├── variables.tf                  # Input variable declarations and defaults
├── outputs.tf                    # Output values (namespace, configmap, context)
├── terraform.tfvars.example      # Example variable values
├── environments/                 # Environment-specific overlays
│   ├── local/                    # Local development configuration
│   └── production/               # Production staging configuration
└── modules/                      # Reusable infrastructure modules
    ├── kubernetes_namespace/     # Declarative namespace creation
    └── app_config/               # Application ConfigMap management
```

## Providers Used

- `hashicorp/kubernetes`: Manages Kubernetes namespaces, ConfigMaps, and cluster-level resources.
- `hashicorp/helm`: Deploys local monitoring releases (Prometheus, Grafana).
- `hashicorp/local`: Manages local configuration artifacts.

## Prerequisites & Architecture Boundaries

Terraform manages declarative definitions inside a local-first or staging Kubernetes cluster:
- **Local Cluster Prerequisite**: A running Kubernetes cluster must be present before executing Terraform. For Docker Desktop, navigate to **Settings > Kubernetes** and enable the Kubernetes feature. For Minikube or Kind, initialize the local cluster beforehand.
- **Provider Role**: The `kubernetes` and `helm` providers communicate with the active cluster context defined in your kubeconfig. Terraform does not install the Docker Desktop application or start the underlying VM.
- **Cost Policy**: The configuration is 100% local-first and does not provision any paid AWS, GCP, or Azure resources.

## Infrastructure Management Workflow

The Terraform workflow follows standard Infrastructure as Code lifecycle phases:
1. Provider initialization and plugin discovery.
2. Declarative execution plan generation against target variables.
3. Resource provisioning and state convergence.
4. Clean teardown and resource decommissioning when required.

## State Management

Terraform state files (`*.tfstate`, `*.tfstate.*`, `.terraform/`) are excluded via `.gitignore` and `.dockerignore`. For team environments, configure a remote state backend (e.g. S3 with DynamoDB locking or HashiCorp Terraform Cloud).

