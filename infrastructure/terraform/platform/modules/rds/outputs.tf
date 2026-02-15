output "rds_endpoint" {
  description = "RDS instance endpoint (without port)"
  value       = split(":", aws_db_instance.main.endpoint)[0]
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "rds_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.main.id
}

output "rds_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.main.arn
}

output "master_username" {
  description = "RDS master username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "airflow_db_name" {
  description = "Airflow database name"
  value       = aws_db_instance.main.db_name
}
