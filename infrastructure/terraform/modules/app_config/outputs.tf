output "configmap_name" {
  description = "Name of the created ConfigMap."
  value       = kubernetes_config_map.architectiq_config.metadata[0].name
}

