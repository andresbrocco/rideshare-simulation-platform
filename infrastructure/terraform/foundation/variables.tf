variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rideshare"
}

variable "domain_name" {
  description = "Domain name for Route 53 and certificates"
  type        = string
  default     = "ridesharing.portfolio.andresbrocco.com"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "github_org" {
  description = "GitHub organization name"
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

variable "parent_domain_name" {
  description = "Parent domain for NS delegation (must already exist as a Route 53 hosted zone)"
  type        = string
  default     = "andresbrocco.com"
}

variable "enable_dns_delegation" {
  description = "Create NS delegation record in parent hosted zone"
  type        = bool
  default     = true
}
