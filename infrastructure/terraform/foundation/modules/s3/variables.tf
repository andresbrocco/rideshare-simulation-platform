variable "project_name" {
  description = "Project name prefix for buckets"
  type        = string
  default     = "rideshare"
}

variable "enable_versioning" {
  description = "Enable versioning on buckets"
  type        = bool
  default     = true
}
