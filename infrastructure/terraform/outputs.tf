output "namespace" {
  description = "The provisioned Kubernetes namespace."
  value       = module.kubernetes_namespace.namespace_name
}

output "environment" {
  description = "The target deployment environment."
  value       = var.environment
}

output "kubernetes_context" {
  description = "The active Kubernetes context utilized."
  value       = var.kubeconfig_context
}

output "configmap_name" {
  description = "The provisioned application ConfigMap name."
  value       = module.app_config.configmap_name
}

