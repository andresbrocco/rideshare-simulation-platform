variable "project_name" {
  description = "Project name prefix for repositories"
  type        = string
  default     = "rideshare"
}

variable "repository_names" {
  description = "List of ECR repository names"
  type        = list(string)
  default = [
    "simulation",
    "stream-processor",
    "frontend",
    "bronze-ingestion",
    "hive-metastore",
    "osrm",
    "otel-collector"
  ]
}

variable "image_retention_count" {
  description = "Number of images to retain"
  type        = number
  default     = 10
}
