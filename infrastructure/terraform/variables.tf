variable "kubeconfig_path" {
  type        = string
  description = "Path to the kubeconfig file for local Kubernetes cluster access."
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  type        = string
  description = "Kubernetes context to target (e.g. docker-desktop, minikube, kind)."
  default     = "docker-desktop"
}

variable "environment" {
  type        = string
  description = "Deployment target environment (local, staging, production)."
  default     = "local"
}

variable "namespace" {
  type        = string
  description = "Kubernetes namespace for ArchitectIQ resources."
  default     = "architectiq"
}

variable "backend_replicas" {
  type        = number
  description = "Number of backend service replicas."
  default     = 2
}

variable "frontend_replicas" {
  type        = number
  description = "Number of frontend service replicas."
  default     = 2
}

variable "enable_monitoring" {
  type        = bool
  description = "Whether to provision Prometheus and Grafana Helm releases."
  default     = true
}

variable "app_labels" {
  type        = map(string)
  description = "Common labels applied to infrastructure resources."
  default = {
    "app.kubernetes.io/name"       = "architectiq"
    "app.kubernetes.io/managed-by" = "terraform"
    "app.kubernetes.io/part-of"    = "architectiq-platform"
  }
}

