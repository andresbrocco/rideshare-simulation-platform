variable "github_org" {
  description = "GitHub organization"
  type        = string
  default     = "andresbrocco"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "rideshare-simulation-platform"
}

variable "github_branch" {
  description = "GitHub branch for OIDC trust"
  type        = string
  default     = "main"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rideshare"
}

variable "s3_bucket_arns" {
  description = "Map of S3 bucket ARNs for IAM policies"
  type = object({
    bronze      = string
    silver      = string
    gold        = string
    checkpoints = string
    tf_state    = string
  })
}

variable "eks_oidc_provider_arn" {
  description = "EKS OIDC provider ARN (placeholder for foundation, actual value from platform)"
  type        = string
  default     = ""
}

variable "eks_oidc_provider_url" {
  description = "EKS OIDC provider URL (placeholder for foundation, actual value from platform)"
  type        = string
  default     = ""
}
