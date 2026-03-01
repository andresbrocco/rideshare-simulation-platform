# Generate random password for RDS master user
resource "random_password" "master_password" {
  length           = 32
  special          = true
  override_special = "!#&*-_=+"
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.project_name}-rds-subnet-group"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "airflow"
  username = "postgres"
  password = random_password.master_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_sg_id]
  publicly_accessible    = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:00-mon:05:00"

  skip_final_snapshot = true

  tags = {
    Name = "${var.project_name}-postgres"
  }
}

# Update Secrets Manager with RDS endpoint
resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = var.rds_secret_id

  secret_string = jsonencode({
    MASTER_USERNAME = aws_db_instance.main.username
    MASTER_PASSWORD = random_password.master_password.result
    ENDPOINT        = aws_db_instance.main.endpoint
    PORT            = aws_db_instance.main.port
  })
}

# Note about metastore database creation
resource "null_resource" "create_metastore_db" {
  provisioner "local-exec" {
    command = <<-EOT
      echo "Database 'metastore' must be created manually or via init script."
      echo "After RDS is running, execute:"
      echo "PGPASSWORD='<password-from-secrets-manager>' psql -h ${aws_db_instance.main.address} -U postgres -d postgres -c 'CREATE DATABASE metastore;'"
    EOT
  }

  depends_on = [
    aws_db_instance.main
  ]
}
