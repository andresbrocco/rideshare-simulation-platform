# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "eks_nodes_sg_id" {
  description = "EKS nodes security group ID"
  value       = module.vpc.eks_nodes_sg_id
}

output "alb_sg_id" {
  description = "ALB security group ID"
  value       = module.vpc.alb_sg_id
}

output "vpc_cidr" {
  description = "VPC CIDR block for security group rules"
  value       = module.vpc.vpc_cidr
}

output "rds_sg_id" {
  description = "RDS security group ID"
  value       = module.vpc.rds_sg_id
}

# -----------------------------------------------------------------------------
# Route 53
# -----------------------------------------------------------------------------
output "route53_zone_id" {
  description = "Route 53 hosted zone ID"
  value       = module.route53.zone_id
}

output "route53_name_servers" {
  description = "Route 53 name servers for domain delegation"
  value       = module.route53.name_servers
}

# -----------------------------------------------------------------------------
# ACM
# -----------------------------------------------------------------------------
output "certificate_arn" {
  description = "ACM certificate ARN"
  value       = module.acm.certificate_arn
}

# -----------------------------------------------------------------------------
# S3
# -----------------------------------------------------------------------------
output "bronze_bucket_name" {
  description = "Bronze S3 bucket name"
  value       = module.s3.bronze_bucket_name
}

output "silver_bucket_name" {
  description = "Silver S3 bucket name"
  value       = module.s3.silver_bucket_name
}

output "gold_bucket_name" {
  description = "Gold S3 bucket name"
  value       = module.s3.gold_bucket_name
}

output "checkpoints_bucket_name" {
  description = "Checkpoints S3 bucket name"
  value       = module.s3.checkpoints_bucket_name
}

output "frontend_bucket_name" {
  description = "Frontend S3 bucket name"
  value       = module.s3.frontend_bucket_name
}

output "logs_bucket_name" {
  description = "Logs S3 bucket name"
  value       = module.s3.logs_bucket_name
}

# -----------------------------------------------------------------------------
# CloudFront
# -----------------------------------------------------------------------------
output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.cloudfront.distribution_id
}

output "cloudfront_distribution_domain" {
  description = "CloudFront distribution domain"
  value       = module.cloudfront.distribution_domain
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------
output "ecr_repository_urls" {
  description = "Map of ECR repository URLs"
  value       = module.ecr.repository_urls
}

# -----------------------------------------------------------------------------
# Lambda
# -----------------------------------------------------------------------------
output "lambda_auth_deploy_url" {
  description = "URL of the Lambda auth/deploy function"
  value       = module.lambda_auth_deploy.function_url
}

output "lambda_auth_deploy_function_name" {
  description = "Name of the Lambda auth/deploy function"
  value       = module.lambda_auth_deploy.function_name
}

# -----------------------------------------------------------------------------
# Secrets Manager
# -----------------------------------------------------------------------------
output "secret_arns" {
  description = "Map of secret ARNs"
  value       = module.secrets_manager.secret_arns
}

output "rds_secret_id" {
  description = "RDS secret ID (for platform module to update endpoint)"
  value       = module.secrets_manager.rds_secret_id
}

# -----------------------------------------------------------------------------
# IAM
# -----------------------------------------------------------------------------
output "github_actions_role_arn" {
  description = "GitHub Actions role ARN"
  value       = module.iam.github_actions_role_arn
}

output "eks_cluster_role_arn" {
  description = "EKS cluster role ARN"
  value       = module.iam.eks_cluster_role_arn
}

output "eks_nodes_role_arn" {
  description = "EKS nodes role ARN"
  value       = module.iam.eks_nodes_role_arn
}

output "simulation_role_arn" {
  description = "Simulation IRSA role ARN"
  value       = module.iam.simulation_role_arn
}

output "bronze_ingestion_role_arn" {
  description = "Bronze ingestion IRSA role ARN"
  value       = module.iam.bronze_ingestion_role_arn
}

output "airflow_role_arn" {
  description = "Airflow IRSA role ARN"
  value       = module.iam.airflow_role_arn
}

output "trino_role_arn" {
  description = "Trino IRSA role ARN"
  value       = module.iam.trino_role_arn
}

output "hive_metastore_role_arn" {
  description = "Hive Metastore IRSA role ARN"
  value       = module.iam.hive_metastore_role_arn
}

output "eso_role_arn" {
  description = "External Secrets Operator IRSA role ARN"
  value       = module.iam.eso_role_arn
}
