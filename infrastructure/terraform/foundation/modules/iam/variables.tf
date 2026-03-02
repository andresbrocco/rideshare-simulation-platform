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
    frontend    = string
    logs        = string
    loki        = string
    tempo       = string
    tf_state    = string
  })
}
