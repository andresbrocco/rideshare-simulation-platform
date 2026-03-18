output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.function.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.function.arn
}

output "function_url" {
  description = "URL of the Lambda Function URL"
  value       = var.enable_function_url ? aws_lambda_function_url.function_url[0].function_url : null
}

output "function_url_id" {
  description = "ID of the Lambda Function URL"
  value       = var.enable_function_url ? aws_lambda_function_url.function_url[0].url_id : null
}

output "role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda.name
}
