# Look up the current AWS account ID for globally unique bucket naming
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------
module "vpc" {
  source = "./modules/vpc"

  project_name       = var.project_name
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# -----------------------------------------------------------------------------
# Route 53 — zone only (alias record created below to avoid circular dependency)
# -----------------------------------------------------------------------------
module "route53" {
  source = "./modules/route53"

  domain_name  = var.domain_name
  project_name = var.project_name
}

# -----------------------------------------------------------------------------
# ACM — must be us-east-1 for CloudFront
# -----------------------------------------------------------------------------
module "acm" {
  source = "./modules/acm"

  providers = {
    aws = aws.us_east_1
  }

  domain_name     = var.domain_name
  route53_zone_id = module.route53.zone_id
}

# -----------------------------------------------------------------------------
# S3
# -----------------------------------------------------------------------------
module "s3" {
  source = "./modules/s3"

  project_name   = var.project_name
  account_suffix = data.aws_caller_identity.current.account_id
}

# -----------------------------------------------------------------------------
# CloudFront
# -----------------------------------------------------------------------------
module "cloudfront" {
  source = "./modules/cloudfront"

  frontend_bucket_name                 = module.s3.frontend_bucket_name
  frontend_bucket_arn                  = module.s3.frontend_bucket_arn
  frontend_bucket_regional_domain_name = module.s3.frontend_bucket_regional_domain_name
  domain_name                          = var.domain_name
  certificate_arn                      = module.acm.certificate_arn
}

# -----------------------------------------------------------------------------
# Route 53 alias record — declared here to break the cycle:
#   route53 → cloudfront → acm → route53
# The zone is created by the route53 module; the alias record points to
# CloudFront and is safe to create after both resources exist.
# -----------------------------------------------------------------------------
resource "aws_route53_record" "cloudfront_apex" {
  zone_id = module.route53.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = module.cloudfront.distribution_domain
    zone_id                = module.cloudfront.distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
}

# -----------------------------------------------------------------------------
# Secrets Manager
# -----------------------------------------------------------------------------
module "secrets_manager" {
  source = "./modules/secrets_manager"

  project_name = var.project_name
}

# -----------------------------------------------------------------------------
# IAM
# -----------------------------------------------------------------------------
module "iam" {
  source = "./modules/iam"

  project_name  = var.project_name
  github_org    = var.github_org
  github_repo   = var.github_repo
  github_branch = var.github_branch

  s3_bucket_arns = {
    bronze      = module.s3.bronze_bucket_arn
    silver      = module.s3.silver_bucket_arn
    gold        = module.s3.gold_bucket_arn
    checkpoints = module.s3.checkpoints_bucket_arn
    frontend    = module.s3.frontend_bucket_arn
    tf_state    = "arn:aws:s3:::rideshare-tf-state-${data.aws_caller_identity.current.account_id}"
  }
}
