output "secret_arns" {
  description = "Map of secret names to ARNs"
  value = {
    api_key            = aws_secretsmanager_secret.api_key.arn
    kafka              = aws_secretsmanager_secret.kafka.arn
    redis              = aws_secretsmanager_secret.redis.arn
    schema_registry    = aws_secretsmanager_secret.schema_registry.arn
    postgres_airflow   = aws_secretsmanager_secret.postgres_airflow.arn
    postgres_metastore = aws_secretsmanager_secret.postgres_metastore.arn
    airflow            = aws_secretsmanager_secret.airflow.arn
    grafana            = aws_secretsmanager_secret.grafana.arn
    rds                = aws_secretsmanager_secret.rds.arn
  }
}

output "secret_names" {
  description = "Map of secret names to full resource names"
  value = {
    api_key            = aws_secretsmanager_secret.api_key.name
    kafka              = aws_secretsmanager_secret.kafka.name
    redis              = aws_secretsmanager_secret.redis.name
    schema_registry    = aws_secretsmanager_secret.schema_registry.name
    postgres_airflow   = aws_secretsmanager_secret.postgres_airflow.name
    postgres_metastore = aws_secretsmanager_secret.postgres_metastore.name
    airflow            = aws_secretsmanager_secret.airflow.name
    grafana            = aws_secretsmanager_secret.grafana.name
    rds                = aws_secretsmanager_secret.rds.name
  }
}

output "rds_secret_id" {
  description = "Secret ID for RDS secret (used by platform module for endpoint update)"
  value       = aws_secretsmanager_secret.rds.id
}
