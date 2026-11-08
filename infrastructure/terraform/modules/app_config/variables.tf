variable "namespace" {
  type        = string
  description = "Target namespace for configuration."
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
}

variable "labels" {
  type        = map(string)
  description = "Labels to apply to the ConfigMap."
  default     = {}
}

