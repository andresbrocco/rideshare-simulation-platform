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

# Secret: rideshare/kafka
resource "aws_secretsmanager_secret" "kafka" {
  name        = "${var.project_name}/kafka"
  description = "Kafka SASL credentials"

  tags = {
    Name = "${var.project_name}/kafka"
  }
}

resource "aws_secretsmanager_secret_version" "kafka" {
  secret_id = aws_secretsmanager_secret.kafka.id

  secret_string = jsonencode({
    KAFKA_SASL_USERNAME = "kafka"
    KAFKA_SASL_PASSWORD = random_password.kafka_password.result
  })
}

# Secret: rideshare/redis
resource "aws_secretsmanager_secret" "redis" {
  name        = "${var.project_name}/redis"
  description = "Redis authentication"

  tags = {
    Name = "${var.project_name}/redis"
  }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id

  secret_string = jsonencode({
    REDIS_PASSWORD = random_password.redis_password.result
  })
}

# Secret: rideshare/schema-registry
resource "aws_secretsmanager_secret" "schema_registry" {
  name        = "${var.project_name}/schema-registry"
  description = "Schema Registry credentials"

  tags = {
    Name = "${var.project_name}/schema-registry"
  }
}

resource "aws_secretsmanager_secret_version" "schema_registry" {
  secret_id = aws_secretsmanager_secret.schema_registry.id

  secret_string = jsonencode({
    SCHEMA_REGISTRY_USER     = "schema-registry"
    SCHEMA_REGISTRY_PASSWORD = random_password.schema_registry_password.result
  })
}

# Secret: rideshare/postgres-airflow
resource "aws_secretsmanager_secret" "postgres_airflow" {
  name        = "${var.project_name}/postgres-airflow"
  description = "Airflow database credentials"

  tags = {
    Name = "${var.project_name}/postgres-airflow"
  }
}

resource "aws_secretsmanager_secret_version" "postgres_airflow" {
  secret_id = aws_secretsmanager_secret.postgres_airflow.id

  secret_string = jsonencode({
    POSTGRES_USER     = "airflow"
    POSTGRES_PASSWORD = random_password.postgres_airflow_password.result
  })
}

# Secret: rideshare/postgres-metastore
resource "aws_secretsmanager_secret" "postgres_metastore" {
  name        = "${var.project_name}/postgres-metastore"
  description = "Hive Metastore database credentials"

  tags = {
    Name = "${var.project_name}/postgres-metastore"
  }
}

resource "aws_secretsmanager_secret_version" "postgres_metastore" {
  secret_id = aws_secretsmanager_secret.postgres_metastore.id

  secret_string = jsonencode({
    POSTGRES_USER     = "metastore"
    POSTGRES_PASSWORD = random_password.postgres_metastore_password.result
  })
}

# Secret: rideshare/airflow
resource "aws_secretsmanager_secret" "airflow" {
  name        = "${var.project_name}/airflow"
  description = "Airflow application secrets"

  tags = {
    Name = "${var.project_name}/airflow"
  }
}

resource "aws_secretsmanager_secret_version" "airflow" {
  secret_id = aws_secretsmanager_secret.airflow.id

  secret_string = jsonencode({
    FERNET_KEY     = random_password.airflow_fernet_key.result
    JWT_SECRET     = random_password.airflow_jwt_secret.result
    API_SECRET_KEY = random_password.airflow_api_secret.result
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = random_password.airflow_admin_password.result
  })
}

# Secret: rideshare/grafana
resource "aws_secretsmanager_secret" "grafana" {
  name        = "${var.project_name}/grafana"
  description = "Grafana admin credentials"

  tags = {
    Name = "${var.project_name}/grafana"
  }
}

resource "aws_secretsmanager_secret_version" "grafana" {
  secret_id = aws_secretsmanager_secret.grafana.id

  secret_string = jsonencode({
    ADMIN_USER     = "admin"
    ADMIN_PASSWORD = random_password.grafana_admin_password.result
  })
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
