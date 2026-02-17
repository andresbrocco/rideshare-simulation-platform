output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.arn
}

output "foundation_init_command" {
  description = "Copy-paste this command to initialize the foundation backend"
  value       = "terraform init -backend-config=\"bucket=${aws_s3_bucket.terraform_state.id}\""
}

output "platform_init_command" {
  description = "Copy-paste this command to initialize the platform backend"
  value       = "terraform init -backend-config=\"bucket=${aws_s3_bucket.terraform_state.id}\""
}
