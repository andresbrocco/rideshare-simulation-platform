variable "route53_zone_id" {
  description = "Route 53 hosted zone ID from foundation"
  type        = string
}

variable "domain_name" {
  description = "Domain name for api subdomain"
  type        = string
}

variable "alb_dns_name" {
  description = "ALB DNS name (placeholder - ALB created by K8s controller)"
  type        = string
  default     = ""
}

variable "alb_zone_id" {
  description = "ALB hosted zone ID (placeholder - ALB created by K8s controller)"
  type        = string
  default     = ""
}
