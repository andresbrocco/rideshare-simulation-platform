variable "domain_name" {
  description = "Primary domain name for ACM certificate"
  type        = string
  default     = "ridesharing.portfolio.andresbrocco.com"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "rideshare"
}

variable "subject_alternative_names" {
  description = "Subject Alternative Names for certificate"
  type        = list(string)
  default     = ["*.ridesharing.portfolio.andresbrocco.com"]
}

variable "route53_zone_id" {
  description = "Route 53 zone ID for DNS validation"
  type        = string
}
