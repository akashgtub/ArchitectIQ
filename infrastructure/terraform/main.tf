# ArchitectIQ - Root Terraform Orchestration

module "kubernetes_namespace" {
  source    = "./modules/kubernetes_namespace"
  namespace = var.namespace
  labels    = merge(var.app_labels, { environment = var.environment })
}

module "app_config" {
  source      = "./modules/app_config"
  namespace   = module.kubernetes_namespace.namespace_name
  environment = var.environment
  labels      = merge(var.app_labels, { environment = var.environment })
}

