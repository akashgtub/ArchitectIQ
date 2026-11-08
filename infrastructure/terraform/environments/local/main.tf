module "architectiq_local" {
  source             = "../../"
  environment        = "local"
  namespace          = "architectiq-local"
  kubeconfig_context = "docker-desktop"
  backend_replicas   = 1
  frontend_replicas  = 1
  enable_monitoring  = true
}

output "namespace" {
  value = module.architectiq_local.namespace
}

