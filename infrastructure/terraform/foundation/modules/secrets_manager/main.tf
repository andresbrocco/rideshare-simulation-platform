# Random passwords for production
resource "random_password" "api_key" {
  length  = 32
  special = true
}

resource "random_password" "kafka_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "redis_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "schema_registry_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "postgres_airflow_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "postgres_metastore_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "airflow_fernet_key" {
  length  = 32
  special = false
}

resource "random_password" "airflow_jwt_secret" {
  length  = var.password_length
  special = true
}

resource "random_password" "airflow_api_secret" {
  length  = var.password_length
  special = true
}

resource "random_password" "airflow_admin_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "grafana_admin_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "minio_root_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "airflow_internal_api_secret_key" {
  length  = var.password_length
  special = true
}

resource "random_password" "hive_ldap_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "ldap_admin_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "ldap_config_password" {
  length  = var.password_length
  special = true
}

resource "random_password" "rds_master_password" {
  length  = var.password_length
  special = true
}

# Secret: rideshare/api-key
resource "aws_secretsmanager_secret" "api_key" {
  name        = "${var.project_name}/api-key"
  description = "API key for simulation service"

  tags = {
    Name = "${var.project_name}/api-key"
  }
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id = aws_secretsmanager_secret.api_key.id

  secret_string = jsonencode({
    API_KEY = random_password.api_key.result
  })
}

# Secret: rideshare/core (merges kafka + redis + schema-registry)
resource "aws_secretsmanager_secret" "core" {
  name        = "${var.project_name}/core"
  description = "Core services credentials (Kafka, Redis, Schema Registry)"

  tags = {
    Name = "${var.project_name}/core"
  }
}

resource "aws_secretsmanager_secret_version" "core" {
  secret_id = aws_secretsmanager_secret.core.id

  secret_string = jsonencode({
    KAFKA_SASL_USERNAME      = "kafka"
    KAFKA_SASL_PASSWORD      = random_password.kafka_password.result
    REDIS_PASSWORD           = random_password.redis_password.result
    SCHEMA_REGISTRY_USER     = "schema-registry"
    SCHEMA_REGISTRY_PASSWORD = random_password.schema_registry_password.result
  })
}

# Secret: rideshare/data-pipeline (merges minio + postgres-airflow + postgres-metastore + airflow + hive-thrift + ldap)
resource "aws_secretsmanager_secret" "data_pipeline" {
  name        = "${var.project_name}/data-pipeline"
  description = "Data pipeline credentials (MinIO, PostgreSQL, Airflow, Hive, LDAP)"

  tags = {
    Name = "${var.project_name}/data-pipeline"
  }
}

resource "aws_secretsmanager_secret_version" "data_pipeline" {
  secret_id = aws_secretsmanager_secret.data_pipeline.id

  secret_string = jsonencode({
    MINIO_ROOT_USER             = "minio"
    MINIO_ROOT_PASSWORD         = random_password.minio_root_password.result
    POSTGRES_AIRFLOW_USER       = "airflow"
    POSTGRES_AIRFLOW_PASSWORD   = random_password.postgres_airflow_password.result
    POSTGRES_METASTORE_USER     = "metastore"
    POSTGRES_METASTORE_PASSWORD = random_password.postgres_metastore_password.result
    FERNET_KEY                  = random_password.airflow_fernet_key.result
    INTERNAL_API_SECRET_KEY     = random_password.airflow_internal_api_secret_key.result
    JWT_SECRET                  = random_password.airflow_jwt_secret.result
    API_SECRET_KEY              = random_password.airflow_api_secret.result
    ADMIN_USERNAME              = "admin"
    ADMIN_PASSWORD              = random_password.airflow_admin_password.result
    HIVE_LDAP_USERNAME          = "admin"
    HIVE_LDAP_PASSWORD          = random_password.hive_ldap_password.result
    LDAP_ADMIN_PASSWORD         = random_password.ldap_admin_password.result
    LDAP_CONFIG_PASSWORD        = random_password.ldap_config_password.result
  })
}

# Secret: rideshare/monitoring (renamed from grafana)
resource "aws_secretsmanager_secret" "monitoring" {
  name        = "${var.project_name}/monitoring"
  description = "Monitoring credentials (Grafana)"

  tags = {
    Name = "${var.project_name}/monitoring"
  }
}

resource "aws_secretsmanager_secret_version" "monitoring" {
  secret_id = aws_secretsmanager_secret.monitoring.id

  secret_string = jsonencode({
    ADMIN_USER     = "admin"
    ADMIN_PASSWORD = random_password.grafana_admin_password.result
  })
}

# Secret: rideshare/github-pat
resource "aws_secretsmanager_secret" "github_pat" {
  name        = "${var.project_name}/github-pat"
  description = "GitHub Personal Access Token for workflow dispatch"

  tags = {
    Name = "${var.project_name}/github-pat"
  }
}

resource "aws_secretsmanager_secret_version" "github_pat" {
  secret_id = aws_secretsmanager_secret.github_pat.id

  secret_string = jsonencode({
    GITHUB_PAT = "ghp_placeholder_set_real_token_in_production"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Secret: rideshare/rds
resource "aws_secretsmanager_secret" "rds" {
  name        = "${var.project_name}/rds"
  description = "RDS master credentials"

  tags = {
    Name = "${var.project_name}/rds"
  }
}

resource "aws_secretsmanager_secret_version" "rds" {
  secret_id = aws_secretsmanager_secret.rds.id

  secret_string = jsonencode({
    MASTER_USERNAME = "rdsadmin"
    MASTER_PASSWORD = random_password.rds_master_password.result
    ENDPOINT        = ""
  })
}
