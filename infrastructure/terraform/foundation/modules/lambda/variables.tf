variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "handler" {
  description = "Lambda function handler (file.function)"
  type        = string
  default     = "handler.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.13"
}

variable "source_dir" {
  description = "Directory containing Lambda function code"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for Lambda function"
  type        = map(string)
  default     = {}
}

variable "timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 14
}

variable "secrets_arns" {
  description = "ARNs of Secrets Manager secrets the function needs to read"
  type        = list(string)
  default     = []
}

variable "cors_allowed_origins" {
  description = "CORS allowed origins for Function URL"
  type        = list(string)
  default     = []
}

variable "cors_allowed_methods" {
  description = "CORS allowed methods for Function URL"
  type        = list(string)
  default     = ["POST"]
}

variable "cors_allowed_headers" {
  description = "CORS allowed headers for Function URL"
  type        = list(string)
  default     = ["Content-Type"]
}

variable "cors_max_age" {
  description = "CORS max age in seconds"
  type        = number
  default     = 86400
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
