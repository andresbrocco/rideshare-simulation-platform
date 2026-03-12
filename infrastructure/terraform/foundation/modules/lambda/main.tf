# Create CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.function_name}-logs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.lambda.arn,
          "${aws_cloudwatch_log_group.lambda.arn}:*"
        ]
      }
    ]
  })
}

# IAM Policy for Secrets Manager
resource "aws_iam_role_policy" "lambda_secrets" {
  count = length(var.secrets_arns) > 0 ? 1 : 0

  name = "${var.function_name}-secrets"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.secrets_arns
      }
    ]
  })
}

# IAM Policy for SSM Parameter Store
resource "aws_iam_role_policy" "lambda_ssm" {
  count = length(var.ssm_parameter_arns) > 0 ? 1 : 0
  name  = "${var.function_name}-ssm"
  role  = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:PutParameter", "ssm:DeleteParameter"]
      Resource = var.ssm_parameter_arns
    }]
  })
}

# IAM Policy for EventBridge Scheduler
resource "aws_iam_role_policy" "lambda_scheduler" {
  count = var.scheduler_config != null ? 1 : 0
  name  = "${var.function_name}-scheduler"
  role  = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["scheduler:CreateSchedule", "scheduler:UpdateSchedule",
        "scheduler:DeleteSchedule", "scheduler:GetSchedule"]
        Resource = var.scheduler_config.schedule_arn_pattern
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = var.scheduler_config.execution_role_arn
      }
    ]
  })
}

# IAM Policy for DynamoDB visitor table
resource "aws_iam_role_policy" "lambda_dynamodb" {
  count = var.enable_dynamodb_policy ? 1 : 0

  name = "${var.function_name}-dynamodb"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# IAM Policy for SES email sending
resource "aws_iam_role_policy" "lambda_ses" {
  count = var.enable_ses_policy ? 1 : 0

  name = "${var.function_name}-ses"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = var.ses_identity_arn
      }
    ]
  })
}

# IAM Policy for writable Secrets Manager secrets (PutSecretValue, CreateSecret)
resource "aws_iam_role_policy" "lambda_writable_secrets" {
  count = length(var.writable_secrets_arns) > 0 ? 1 : 0

  name = "${var.function_name}-writable-secrets"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:PutSecretValue",
          "secretsmanager:CreateSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.writable_secrets_arns
      }
    ]
  })
}

# IAM Policy for S3 bucket access
resource "aws_iam_role_policy" "lambda_s3" {
  count = var.enable_s3_policy ? 1 : 0

  name = "${var.function_name}-s3"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [for arn in var.s3_bucket_arns : "${arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = var.s3_bucket_arns
      }
    ]
  })
}

# IAM Policy for KMS encrypt/decrypt (visitor password encryption)
resource "aws_iam_role_policy" "lambda_kms" {
  count = var.enable_kms_policy ? 1 : 0

  name = "${var.function_name}-kms"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# Package Lambda function code
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda Function
resource "aws_lambda_function" "function" {
  filename                       = data.archive_file.lambda.output_path
  function_name                  = var.function_name
  role                           = aws_iam_role.lambda.arn
  handler                        = var.handler
  source_code_hash               = data.archive_file.lambda.output_base64sha256
  runtime                        = var.runtime
  timeout                        = var.timeout
  memory_size                    = var.memory_size
  reserved_concurrent_executions = var.reserved_concurrent_executions

  environment {
    variables = var.environment_variables
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda_logs
  ]

  tags = var.tags
}

# Lambda Function URL
resource "aws_lambda_function_url" "function_url" {
  function_name      = aws_lambda_function.function.function_name
  authorization_type = "NONE" # Public access, auth handled in function

  cors {
    allow_origins     = var.cors_allowed_origins
    allow_methods     = var.cors_allowed_methods
    allow_headers     = var.cors_allowed_headers
    max_age           = var.cors_max_age
    allow_credentials = false
  }
}

# CloudWatch Alarm for Errors
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Lambda function has more than 5 errors in 10 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.function.function_name
  }

  tags = var.tags
}

# CloudWatch Alarm for Throttles
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.function_name}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alert when Lambda function is throttled"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.function.function_name
  }

  tags = var.tags
}
