# ArchitectIQ — Ansible Configuration Management

This directory provides configuration management and deployment orchestration for **ArchitectIQ**.

## Role Separation & Responsibility

- **Terraform**: Manages cluster infrastructure (namespaces, ingress controllers, storage definitions).
- **Ansible**: Prepares deployment host environments, verifies container engines, configures application environments, and manages configuration templates.
- **Kubernetes**: Manages container lifecycles, service discovery, rolling updates, and self-healing.
- **Jenkins**: Coordinates the end-to-end automation pipeline.

## Directory Structure

```text
infrastructure/ansible/
├── ansible.cfg              # Ansible configuration
├── inventory/               # Environment inventories
│   ├── hosts.ini            # Default inventory
│   ├── local                # Local development inventory
│   └── production           # Production cluster inventory
├── group_vars/              # Environment-specific variables
│   ├── all.yml              # Global defaults
│   ├── local.yml            # Local overrides
│   └── production.yml       # Production overrides
├── roles/                   # Modular roles
│   ├── environment_setup/   # File paths and base directory creation
│   ├── container_runtime/   # Docker daemon & runtime validation
│   ├── kubernetes_readiness/# Kubeconfig and namespace verification
│   ├── app_configuration/   # Application config file generation
│   ├── monitoring_setup/    # Prometheus / Grafana setup
│   └── deployment_support/  # Deployment metadata registration
└── playbooks/               # Top-level playbooks
    ├── site.yml             # Full master execution playbook
    ├── provision_env.yml    # Environment preparation only
    ├── deploy_app.yml       # Application deployment configuration
    └── configure_monitoring.yml # Monitoring configuration
```

## Configuration Management Workflow

The configuration lifecycle operates across several phases:
1. Inventory evaluation and dynamic host variable resolution.
2. Playbook execution applying modular roles to target environments.
3. Syntax verification and dry-run validation prior to production changes.

