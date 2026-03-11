# CONTEXT.md — Lambda Module

## Purpose

Reusable Terraform module that provisions a complete AWS Lambda function deployment unit. Used by the foundation layer to create the `rideshare-auth-deploy` function, which handles API key validation and EventBridge Scheduler management for the platform's deploy/teardown workflow.

## Responsibility Boundaries

- **Owns**: Lambda function resource, execution IAM role, CloudWatch log group (with retention), Function URL with CORS, CloudWatch alarms for errors and throttles, conditional IAM policies for Secrets Manager (read-only and writable), SSM Parameter Store, EventBridge Scheduler, DynamoDB, SES, and KMS
- **Delegates to**: Callers to supply the function source directory (`source_dir`), handler, and any optional permission ARNs
- **Does not handle**: API Gateway integration, VPC networking, Lambda layers, reserved concurrency, or aliases/versioning

## Key Concepts

- **Function URL**: The module always creates a Lambda Function URL (`authorization_type = "NONE"`), not an API Gateway trigger. Auth is handled inside the function itself, not at the AWS layer.
- **Conditional IAM policies**: Policies for Secrets Manager (`secrets_arns`), SSM Parameter Store (`ssm_parameter_arns`), and EventBridge Scheduler (`scheduler_config`) are only created when the caller supplies non-empty values. DynamoDB, SES, and KMS policies use explicit boolean flags (`enable_dynamodb_policy`, `enable_ses_policy`, `enable_kms_policy`) rather than ARN-emptiness checks, avoiding plan-time unknown-value issues with computed ARNs. This keeps the IAM surface minimal by default.
- **EventBridge Scheduler integration**: When `scheduler_config` is provided, the function receives permissions to manage EventBridge Scheduler schedules (create/update/delete/get) and to pass the scheduler execution role. This supports the auth-deploy function's ability to create time-bounded teardown schedules.
- **Writable secrets policy**: Separate from the read-only `secrets_arns` policy, `writable_secrets_arns` grants `PutSecretValue`/`CreateSecret` in addition to read permissions. Used when the Lambda must write provisioned credentials back to Secrets Manager (e.g., visitor provisioning flow).
- **DynamoDB policy**: Grants `PutItem`/`GetItem`/`Scan`/`UpdateItem` on a single table ARN. Enabled via `enable_dynamodb_policy = true` alongside `dynamodb_table_arn`.
- **SES policy**: Grants `SendEmail`/`SendRawEmail` against a single SES domain identity ARN. Enabled via `enable_ses_policy = true` alongside `ses_identity_arn`.
- **KMS policy**: Grants `Encrypt`/`Decrypt`/`GenerateDataKey` on a single KMS key ARN. Enabled via `enable_kms_policy = true` alongside `kms_key_arn`.

## Non-Obvious Details

- The `archive_file` data source zips `source_dir` at plan time and writes `lambda_function.zip` into the module directory itself. The committed `lambda_function.zip` in this directory is an artifact of this packaging step.
- CloudWatch alarms are unconditionally created: errors alarm triggers at >5 errors in 10 minutes (2 evaluation periods of 5 min); throttles alarm triggers at any throttle (threshold=0). Both use `treat_missing_data = "notBreaching"`, so periods with no invocations do not fire.
- The module does not create the EventBridge Scheduler execution role — that role is created in `foundation/main.tf` and passed in via `scheduler_config.execution_role_arn`. The module only grants the Lambda permission to `iam:PassRole` that pre-existing role.
- CORS `allow_credentials` is hardcoded to `false`; callers cannot override this.
