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
# DNS delegation — create NS record in parent zone for subdomain resolution
# -----------------------------------------------------------------------------
data "aws_route53_zone" "parent" {
  count = var.enable_dns_delegation ? 1 : 0

  name         = var.parent_domain_name
  private_zone = false
}

resource "aws_route53_record" "ns_delegation" {
  count = var.enable_dns_delegation ? 1 : 0

  zone_id = data.aws_route53_zone.parent[0].zone_id
  name    = var.domain_name
  type    = "NS"
  ttl     = 172800

  records = module.route53.name_servers
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
# EventBridge Scheduler execution role — invokes the Lambda on schedule
# -----------------------------------------------------------------------------
resource "aws_iam_role" "scheduler_execution" {
  name = "rideshare-scheduler-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = ["sts:AssumeRole"]
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
  tags = { Project = var.project_name, Component = "scheduler" }
}

resource "aws_iam_role_policy" "scheduler_invoke_lambda" {
  name = "rideshare-scheduler-invoke"
  role = aws_iam_role.scheduler_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:rideshare-auth-deploy"
    }]
  })
}

# -----------------------------------------------------------------------------
# Lambda — auth validation and deploy triggering
# -----------------------------------------------------------------------------
module "lambda_auth_deploy" {
  source = "./modules/lambda"

  function_name = "rideshare-auth-deploy"
  source_dir    = "${path.root}/../../lambda/auth-deploy"
  handler       = "handler.lambda_handler"
  runtime       = "python3.13"
  timeout       = 30
  memory_size   = 256

  environment_variables = {
    SCHEDULER_ROLE_ARN       = aws_iam_role.scheduler_execution.arn
    SELF_FUNCTION_ARN        = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:rideshare-auth-deploy"
    KMS_VISITOR_PASSWORD_KEY = aws_kms_key.visitors.arn
  }

  # Grant read access to API key and GitHub PAT secrets
  secrets_arns = [
    module.secrets_manager.secret_arns["api_key"],
    module.secrets_manager.secret_arns["github_pat"],
  ]

  ssm_parameter_arns = [
    "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rideshare/session/*"
  ]

  scheduler_config = {
    schedule_arn_pattern = "arn:aws:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/default/rideshare-*"
    execution_role_arn   = aws_iam_role.scheduler_execution.arn
  }

  # CORS configuration for frontend
  cors_allowed_origins = [
    "https://ridesharing.portfolio.andresbrocco.com",
    "https://control-panel.ridesharing.portfolio.andresbrocco.com",
    "http://localhost:5173",
  ]
  cors_allowed_methods = ["*"]
  cors_allowed_headers = ["Content-Type", "X-Requested-With"]
  cors_max_age         = 86400

  dynamodb_table_arn = aws_dynamodb_table.visitors.arn
  ses_identity_arn   = aws_ses_domain_identity.main.arn
  kms_key_arn        = aws_kms_key.visitors.arn

  log_retention_days = 14

  tags = {
    Project   = var.project_name
    Component = "auth-deploy"
  }
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
    bronze       = module.s3.bronze_bucket_arn
    silver       = module.s3.silver_bucket_arn
    gold         = module.s3.gold_bucket_arn
    checkpoints  = module.s3.checkpoints_bucket_arn
    build_assets = module.s3.build_assets_bucket_arn
    frontend     = module.s3.frontend_bucket_arn
    logs         = module.s3.logs_bucket_arn
    loki         = module.s3.loki_bucket_arn
    tempo        = module.s3.tempo_bucket_arn
    tf_state     = "arn:aws:s3:::rideshare-tf-state-${data.aws_caller_identity.current.account_id}"
  }
}

# -----------------------------------------------------------------------------
# Glue Data Catalog
# -----------------------------------------------------------------------------
resource "aws_glue_catalog_database" "bronze" {
  name        = "${var.project_name}_bronze"
  description = "Raw ingested events — Bronze medallion layer"

  tags = { Project = var.project_name, Component = "glue-catalog" }
}

resource "aws_glue_catalog_database" "silver" {
  name        = "${var.project_name}_silver"
  description = "Cleaned and deduplicated events — Silver medallion layer"

  tags = { Project = var.project_name, Component = "glue-catalog" }
}

resource "aws_glue_catalog_database" "gold" {
  name        = "${var.project_name}_gold"
  description = "Star-schema aggregates for analytics — Gold medallion layer"

  tags = { Project = var.project_name, Component = "glue-catalog" }
}

# -----------------------------------------------------------------------------
# KMS — encryption key for visitor data at rest
# -----------------------------------------------------------------------------
resource "aws_kms_key" "visitors" {
  description             = "CMK for ${var.project_name} visitor provisioning data"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowRootFullAccess"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      }
    ]
  })

  tags = { Project = var.project_name, Component = "visitor-provisioning" }
}

resource "aws_kms_alias" "visitors" {
  name          = "alias/rideshare-visitor-passwords"
  target_key_id = aws_kms_key.visitors.key_id
}

# -----------------------------------------------------------------------------
# DynamoDB — visitor provisioning records (persist across platform deploys)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "visitors" {
  name         = "${var.project_name}-visitors"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.visitors.arn
  }

  tags = { Project = var.project_name, Component = "visitor-provisioning" }
}

# -----------------------------------------------------------------------------
# SES — domain identity for sending welcome emails
# -----------------------------------------------------------------------------
resource "aws_ses_domain_identity" "main" {
  domain = var.domain_name
}

resource "aws_route53_record" "ses_verification" {
  zone_id = module.route53.zone_id
  name    = "_amazonses.${var.domain_name}"
  type    = "TXT"
  ttl     = 600
  records = [aws_ses_domain_identity.main.verification_token]
}
