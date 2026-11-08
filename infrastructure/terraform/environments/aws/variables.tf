variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "architectiq"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}