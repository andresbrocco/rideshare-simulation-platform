variable "domain_name" {
  description = "Domain name for hosted zone"
  type        = string
  default     = "ridesharing.portfolio.andresbrocco.com"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "rideshare"
}

variable "cloudfront_distribution_domain_name" {
  description = "CloudFront distribution domain name for apex alias record"
  type        = string
  default     = ""
}

variable "cloudfront_distribution_hosted_zone_id" {
  description = "CloudFront distribution hosted zone ID for apex alias record"
  type        = string
  default     = ""
}
