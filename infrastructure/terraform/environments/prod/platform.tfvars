aws_region   = "us-east-1"
project_name = "rideshare"
domain_name  = "ridesharing.portfolio.andresbrocco.com"

# EKS Configuration
cluster_version    = "1.31"
node_instance_type = "t3.xlarge"
node_count         = 3
node_disk_size     = 50

# RDS Configuration
postgres_version   = "16.6"
rds_instance_class = "db.t4g.micro"
