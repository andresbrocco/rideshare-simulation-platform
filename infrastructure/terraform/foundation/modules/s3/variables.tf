variable "project_name" {
  description = "Project name prefix for buckets"
  type        = string
  default     = "rideshare"
}

variable "account_suffix" {
  description = "AWS account ID appended to bucket names for global uniqueness"
  type        = string
}

variable "enable_versioning" {
  description = "Enable versioning on buckets"
  type        = bool
  default     = true
}
