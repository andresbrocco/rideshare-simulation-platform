variable "frontend_bucket_name" {
  description = "Name of S3 bucket for frontend"
  type        = string
}

variable "frontend_bucket_arn" {
  description = "ARN of S3 bucket for frontend"
  type        = string
}

variable "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of frontend bucket"
  type        = string
}

variable "domain_name" {
  description = "Domain name for CloudFront"
  type        = string
  default     = "ridesharing.portfolio.andresbrocco.com"
}

variable "certificate_arn" {
  description = "ACM certificate ARN (must be in us-east-1)"
  type        = string
}
