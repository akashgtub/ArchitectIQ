# ArchitectIQ — Ansible Configuration Management Guide

## 1. Overview

Ansible manages configuration management, deployment preparation, and environment validation for **ArchitectIQ**. It bridges the gap between infrastructure provisioning (Terraform) and container orchestration (Kubernetes).

---

## 2. Directory Layout & Architecture

```text
infrastructure/ansible/
├── ansible.cfg              # Default inventory, callback plugins, timeouts
├── inventory/               # Inventory definitions
│   ├── hosts.ini            # Base hosts inventory
│   ├── local                # Local development variables
│   └── production           # Production cluster node variables
├── group_vars/              # Variable scoping
│   ├── all.yml              # Global ports, images, health paths
│   ├── local.yml            # Local replica counts and log levels
│   └── production.yml       # Production replicas and configurations
├── roles/                   # Reusable modular roles
│   ├── environment_setup/   # File system directory creation
│   ├── container_runtime/   # Docker daemon & runtime validation
│   ├── kubernetes_readiness/# Kubeconfig and namespace verification
│   ├── app_configuration/   # Application config file generation
│   ├── monitoring_setup/    # Prometheus / Grafana setup
│   └── deployment_support/  # Deployment metadata registration
└── playbooks/               # Playbook workflows
    ├── site.yml             # Full master execution playbook
    ├── provision_env.yml    # Environment preparation only
    ├── deploy_app.yml       # Application deployment configuration
    └── configure_monitoring.yml # Monitoring configuration
```

---

## 3. Role Breakdown

1. **`environment_setup`**: Ensures deployment directories (`/etc/architectiq`, `/var/log/architectiq`) exist with correct permissions (`0755`).
2. **`container_runtime`**: Verifies container socket accessibility (`/var/run/docker.sock`) and container engine health.
3. **`kubernetes_readiness`**: Confirms that valid Kubeconfig files are present and can authenticate against the target cluster.
4. **`app_configuration`**: Renders environment configuration templates (`architectiq.env`) for container runtime consumption.
5. **`monitoring_setup`**: Validates Prometheus scrape target syntax and Grafana provisioning paths.
6. **`deployment_support`**: Registers deployment metadata, image versions, and replica parameters.

---

## 4. Execution Workflow (Documentation Reference Only)

```bash
ansible-inventory -i infrastructure/ansible/inventory/local --list

ansible-playbook -i infrastructure/ansible/inventory/local infrastructure/ansible/playbooks/site.yml --syntax-check

ansible-playbook -i infrastructure/ansible/inventory/local infrastructure/ansible/playbooks/site.yml --check

ansible-playbook -i infrastructure/ansible/inventory/local infrastructure/ansible/playbooks/site.yml
```

