data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  value = data.aws_region.current.region
}

output "terraform_identity" {
  value = data.aws_caller_identity.current.arn
}