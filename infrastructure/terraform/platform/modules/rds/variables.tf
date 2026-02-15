variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rideshare"
}

variable "postgres_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.6"
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "subnet_ids" {
  description = "Subnet IDs for DB subnet group"
  type        = list(string)
}

variable "rds_sg_id" {
  description = "Security group ID for RDS from foundation"
  type        = string
}

variable "rds_secret_id" {
  description = "Secrets Manager secret ID for RDS credentials (from foundation)"
  type        = string
}
