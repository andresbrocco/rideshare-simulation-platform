output "secret_arns" {
  description = "Map of secret names to ARNs"
  value = {
    api_key       = aws_secretsmanager_secret.api_key.arn
    core          = aws_secretsmanager_secret.core.arn
    data_pipeline = aws_secretsmanager_secret.data_pipeline.arn
    monitoring    = aws_secretsmanager_secret.monitoring.arn
    github_pat    = aws_secretsmanager_secret.github_pat.arn
    rds           = aws_secretsmanager_secret.rds.arn
    admin_user    = aws_secretsmanager_secret.admin_user.arn
    llm_api_key   = aws_secretsmanager_secret.llm_api_key.arn
  }
}

output "secret_names" {
  description = "Map of secret names to full resource names"
  value = {
    api_key       = aws_secretsmanager_secret.api_key.name
    core          = aws_secretsmanager_secret.core.name
    data_pipeline = aws_secretsmanager_secret.data_pipeline.name
    monitoring    = aws_secretsmanager_secret.monitoring.name
    github_pat    = aws_secretsmanager_secret.github_pat.name
    rds           = aws_secretsmanager_secret.rds.name
    admin_user    = aws_secretsmanager_secret.admin_user.name
    llm_api_key   = aws_secretsmanager_secret.llm_api_key.name
  }
}

output "rds_secret_id" {
  description = "Secret ID for RDS secret (used by platform module for endpoint update)"
  value       = aws_secretsmanager_secret.rds.id
}

output "admin_user_password" {
  description = "Generated admin user password"
  value       = random_password.admin_user_password.result
  sensitive   = true
}
