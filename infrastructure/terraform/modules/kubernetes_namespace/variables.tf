variable "namespace" {
  type        = string
  description = "Name of the Kubernetes namespace."
}

variable "labels" {
  type        = map(string)
  description = "Labels to apply to the namespace."
  default     = {}
}

