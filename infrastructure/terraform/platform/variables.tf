variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "rideshare"
}

variable "domain_name" {
  description = "Domain name"
  type        = string
  default     = "ridesharing.portfolio.andresbrocco.com"
}

variable "cluster_version" {
  description = "EKS cluster version"
  type        = string
  default     = "1.33"
}

variable "node_instance_type" {
  description = "EKS node instance type"
  type        = string
  default     = "t3.xlarge"
}

variable "node_count" {
  description = "Number of EKS nodes"
  type        = number
  default     = 3
}

variable "node_disk_size" {
  description = "EKS node disk size (GB)"
  type        = number
  default     = 50
}

variable "postgres_version" {
  description = "RDS PostgreSQL version"
  type        = string
  default     = "16.6"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}
