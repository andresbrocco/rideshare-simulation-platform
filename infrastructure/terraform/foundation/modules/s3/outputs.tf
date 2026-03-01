output "bronze_bucket_name" {
  description = "Name of bronze S3 bucket"
  value       = aws_s3_bucket.bronze.id
}

output "bronze_bucket_arn" {
  description = "ARN of bronze S3 bucket"
  value       = aws_s3_bucket.bronze.arn
}

output "silver_bucket_name" {
  description = "Name of silver S3 bucket"
  value       = aws_s3_bucket.silver.id
}

output "silver_bucket_arn" {
  description = "ARN of silver S3 bucket"
  value       = aws_s3_bucket.silver.arn
}

output "gold_bucket_name" {
  description = "Name of gold S3 bucket"
  value       = aws_s3_bucket.gold.id
}

output "gold_bucket_arn" {
  description = "ARN of gold S3 bucket"
  value       = aws_s3_bucket.gold.arn
}

output "checkpoints_bucket_name" {
  description = "Name of checkpoints S3 bucket"
  value       = aws_s3_bucket.checkpoints.id
}

output "checkpoints_bucket_arn" {
  description = "ARN of checkpoints S3 bucket"
  value       = aws_s3_bucket.checkpoints.arn
}

output "frontend_bucket_name" {
  description = "Name of frontend S3 bucket"
  value       = aws_s3_bucket.frontend.id
}

output "frontend_bucket_arn" {
  description = "ARN of frontend S3 bucket"
  value       = aws_s3_bucket.frontend.arn
}

output "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of frontend bucket"
  value       = aws_s3_bucket.frontend.bucket_regional_domain_name
}

output "logs_bucket_name" {
  description = "Name of logs S3 bucket"
  value       = aws_s3_bucket.logs.id
}

output "logs_bucket_arn" {
  description = "ARN of logs S3 bucket"
  value       = aws_s3_bucket.logs.arn
}
