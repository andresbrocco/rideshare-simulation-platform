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

output "logs_bucket_arn" {
  description = "Logs S3 bucket ARN"
  value       = module.s3.logs_bucket_arn
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

output "lambda_ai_chat_url" {
  description = "URL of the Lambda ai-chat function"
  value       = module.lambda_ai_chat.function_url
}

output "lambda_ai_chat_function_name" {
  description = "Name of the Lambda ai-chat function"
  value       = module.lambda_ai_chat.function_name
}

output "lambda_rds_reset_function_name" {
  description = "Name of the Lambda RDS reset function"
  value       = module.lambda_rds_reset.function_name
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

output "loki_role_arn" {
  description = "Loki IRSA role ARN"
  value       = module.iam.loki_role_arn
}

output "tempo_role_arn" {
  description = "Tempo IRSA role ARN"
  value       = module.iam.tempo_role_arn
}

output "loki_bucket_name" {
  description = "Loki S3 bucket name"
  value       = module.s3.loki_bucket_name
}

output "tempo_bucket_name" {
  description = "Tempo S3 bucket name"
  value       = module.s3.tempo_bucket_name
}

output "eso_role_arn" {
  description = "External Secrets Operator IRSA role ARN"
  value       = module.iam.eso_role_arn
}

output "glue_job_role_arn" {
  description = "Glue Job Execution role ARN (passed to Glue Interactive Sessions)"
  value       = module.iam.glue_job_role_arn
}

# -----------------------------------------------------------------------------
# Glue Data Catalog
# -----------------------------------------------------------------------------
output "glue_bronze_database_name" {
  description = "Glue Data Catalog database name for the Bronze layer"
  value       = aws_glue_catalog_database.bronze.name
}

output "glue_silver_database_name" {
  description = "Glue Data Catalog database name for the Silver layer"
  value       = aws_glue_catalog_database.silver.name
}

output "glue_gold_database_name" {
  description = "Glue Data Catalog database name for the Gold layer"
  value       = aws_glue_catalog_database.gold.name
}

# -----------------------------------------------------------------------------
# DynamoDB
# -----------------------------------------------------------------------------
output "visitors_table_arn" {
  description = "ARN of the DynamoDB visitors table"
  value       = aws_dynamodb_table.visitors.arn
}

output "visitors_table_name" {
  description = "Name of the DynamoDB visitors table"
  value       = aws_dynamodb_table.visitors.name
}

# -----------------------------------------------------------------------------
# SES
# -----------------------------------------------------------------------------
output "ses_domain_identity_arn" {
  description = "ARN of the SES domain identity"
  value       = aws_ses_domain_identity.main.arn
}

# -----------------------------------------------------------------------------
# Admin User
# -----------------------------------------------------------------------------
output "admin_password" {
  description = "Generated admin user password for control panel login"
  value       = module.secrets_manager.admin_user_password
  sensitive   = true
}
