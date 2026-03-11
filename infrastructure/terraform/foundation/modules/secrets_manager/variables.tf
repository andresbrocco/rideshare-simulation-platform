variable "project_name" {
  description = "Project name for secret naming"
  type        = string
  default     = "rideshare"
}

variable "password_length" {
  description = "Length of generated passwords"
  type        = number
  default     = 16
}

variable "admin_email" {
  description = "Admin user email address for control panel login"
  type        = string
}
