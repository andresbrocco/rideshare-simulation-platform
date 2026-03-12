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

variable "ssm_parameter_arns" {
  description = "ARNs of SSM parameters the function can read/write/delete"
  type        = list(string)
  default     = []
}

variable "scheduler_config" {
  description = "EventBridge Scheduler permissions config"
  type = object({
    schedule_arn_pattern = string
    execution_role_arn   = string
  })
  default = null
}

variable "dynamodb_table_arn" {
  description = "ARN of DynamoDB table the function needs read/write access to. Leave empty to skip policy."
  type        = string
  default     = ""
}

variable "enable_dynamodb_policy" {
  description = "Whether to create the DynamoDB IAM policy. Use this instead of relying on dynamodb_table_arn emptiness checks to avoid plan-time unknown value issues."
  type        = bool
  default     = false
}

variable "ses_identity_arn" {
  description = "ARN of SES domain identity the function may send email from. Leave empty to skip policy."
  type        = string
  default     = ""
}

variable "enable_ses_policy" {
  description = "Whether to create the SES IAM policy."
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "ARN of KMS key the function may use for Encrypt/Decrypt. Leave empty to skip policy."
  type        = string
  default     = ""
}

variable "enable_kms_policy" {
  description = "Whether to create the KMS IAM policy."
  type        = bool
  default     = false
}

variable "writable_secrets_arns" {
  description = "ARNs of Secrets Manager secrets the function needs write access to (PutSecretValue, CreateSecret)"
  type        = list(string)
  default     = []
}

variable "s3_bucket_arns" {
  description = "ARNs of S3 buckets the function needs read/write access to. Leave empty to skip policy."
  type        = list(string)
  default     = []
}

variable "enable_s3_policy" {
  description = "Whether to create the S3 IAM policy. Use this instead of relying on s3_bucket_arns emptiness to avoid plan-time unknown value issues."
  type        = bool
  default     = false
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrent executions for the Lambda function. -1 means unreserved (account default)."
  type        = number
  default     = -1
}
