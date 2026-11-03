module "architectiq_production" {
  source             = "../../"
  environment        = "production"
  namespace          = "architectiq"
  kubeconfig_context = "docker-desktop"
  backend_replicas   = 2
  frontend_replicas  = 2
  enable_monitoring  = true
}

output "namespace" {
  value = module.architectiq_production.namespace
}

