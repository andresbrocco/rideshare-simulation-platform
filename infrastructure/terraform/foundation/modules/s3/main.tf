locals {
  bucket_prefix = "${var.project_name}-${var.account_suffix}"
}

# Bronze Bucket (raw events)
resource "aws_s3_bucket" "bronze" {
  bucket = "${local.bucket_prefix}-bronze"

  tags = {
    Name  = "${local.bucket_prefix}-bronze"
    Layer = "bronze"
  }
}

resource "aws_s3_bucket_versioning" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "bronze" {
  bucket = aws_s3_bucket.bronze.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Silver Bucket (cleaned/validated events)
resource "aws_s3_bucket" "silver" {
  bucket = "${local.bucket_prefix}-silver"

  tags = {
    Name  = "${local.bucket_prefix}-silver"
    Layer = "silver"
  }
}

resource "aws_s3_bucket_versioning" "silver" {
  bucket = aws_s3_bucket.silver.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket = aws_s3_bucket.silver.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Gold Bucket (star schema analytics)
resource "aws_s3_bucket" "gold" {
  bucket = "${local.bucket_prefix}-gold"

  tags = {
    Name  = "${local.bucket_prefix}-gold"
    Layer = "gold"
  }
}

resource "aws_s3_bucket_versioning" "gold" {
  bucket = aws_s3_bucket.gold.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_public_access_block" "gold" {
  bucket = aws_s3_bucket.gold.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Checkpoints Bucket (simulation state)
resource "aws_s3_bucket" "checkpoints" {
  bucket = "${local.bucket_prefix}-checkpoints"

  tags = {
    Name    = "${local.bucket_prefix}-checkpoints"
    Purpose = "simulation-state"
  }
}

resource "aws_s3_bucket_versioning" "checkpoints" {
  bucket = aws_s3_bucket.checkpoints.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "checkpoints" {
  bucket = aws_s3_bucket.checkpoints.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Frontend Bucket (static React SPA)
resource "aws_s3_bucket" "frontend" {
  bucket = "${local.bucket_prefix}-frontend"

  tags = {
    Name    = "${local.bucket_prefix}-frontend"
    Purpose = "static-website"
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule for lakehouse buckets (delete old versions after 90 days)
resource "aws_s3_bucket_lifecycle_configuration" "lakehouse" {
  for_each = {
    bronze = aws_s3_bucket.bronze.id
    silver = aws_s3_bucket.silver.id
    gold   = aws_s3_bucket.gold.id
  }

  bucket = each.value

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}
