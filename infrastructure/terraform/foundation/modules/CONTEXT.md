# CONTEXT.md — Foundation Modules

## Purpose

Reusable Terraform modules that provision the AWS account-level and network-level infrastructure shared across all environments. These modules define the durable substrate — networking, identity, storage, CDN, secrets, and container registry — upon which the platform layer (EKS, RDS, ALB) is built.

## Responsibility Boundaries

- **Owns**: VPC topology and security groups, all S3 buckets, IAM roles and their policies for every workload and CI, ACM certificate provisioning, CloudFront distribution for the React SPA, ECR repositories, Secrets Manager secrets with generated credentials, Lambda function wrapper with conditional IAM policies for Secrets Manager (read-only and writable), SSM Parameter Store, EventBridge Scheduler, DynamoDB, SES, and KMS
- **Delegates to**: `infrastructure/terraform/platform` for EKS cluster, node groups, RDS, and ALB; `infrastructure/terraform/bootstrap` for the S3 Terraform state backend itself
- **Does not handle**: Kubernetes resources, ArgoCD, application configuration, or environment-specific overrides

## Key Concepts

- **Pod Identity**: All workload IAM roles (`simulation`, `bronze-ingestion`, `airflow`, `trino`, `hive-metastore`, `loki`, `tempo`, `eso`) use EKS Pod Identity (`pods.eks.amazonaws.com` trust + `sts:TagSession`), not IRSA. Pod Identity associations are wired in the platform module.
- **GitHub OIDC**: The CI/CD role (`github-actions`) uses OIDC web identity federation, not static keys. Trust is scoped to a specific repository and branch via `token.actions.githubusercontent.com:sub` condition.
- **Glue job role split**: The `glue-job` role trusts `glue.amazonaws.com`, not Pod Identity. The `airflow` Pod Identity role holds `iam:PassRole` permission to delegate sessions to it. This two-role pattern is required because Glue Interactive Sessions are Glue-service-side, not pod-side.
- **Secret grouping**: Secrets are bundled by service group (`core`, `data-pipeline`, `monitoring`, `rds`) rather than one secret per service. This reduces External Secrets Operator `SecretStore` round-trips and keeps related credentials co-located.
- **Lambda-managed secrets (outside Terraform state)**: Two Trino password-hash secrets are created at runtime, not by Terraform: `{project}/trino-admin-password-hash` is written by the deploy workflow, and `{project}/trino-visitor-password-hash` is written on demand by the provisioning Lambda. These are intentionally absent from Terraform state — do not import or manage them here.

## Non-Obvious Details

- **ACM module must use `aws.us_east_1` provider alias**: CloudFront requires TLS certificates in us-east-1 regardless of the cluster's region. The module file comment states this explicitly, but callers must pass `providers = { aws = aws.us_east_1 }` or certificate validation will fail silently in another region.
- **VPC is public-subnet-only**: There are no private subnets or NAT gateways. EKS nodes receive public IPs but are protected by security groups. This is a deliberate cost reduction — private subnets with NAT would add ~$0.045/hr per AZ.
- **Node-level Secrets Manager policy**: The `eks_nodes` role has a `secretsmanager:GetSecretValue` inline policy in addition to the `eso` Pod Identity role. The comment explains why: External Secrets Operator may not be schedulable during initial cluster bootstrap before the Pod Identity webhook is available.
- **`build_assets` bucket survives soft resets**: The soft-reset workflow deletes bronze/silver/gold/checkpoints but not `build_assets`, which caches OSRM map data between CI runs.
- **`lambda_function.zip` is committed**: The `lambda` module builds a zip artifact at `path.module/lambda_function.zip` via `archive_file`. This file is regenerated on `terraform apply`; the committed copy is a Terraform-managed output artifact, not source.
- **CloudFront uses OAC, not OAI**: The `cloudfront` module uses Origin Access Control (`aws_cloudfront_origin_access_control`) with SigV4 signing rather than the deprecated Origin Access Identity pattern.
- **`secrets_manager` github-pat has `ignore_changes`**: The placeholder value (`ghp_placeholder_...`) is set only on initial creation. Terraform ignores subsequent changes so that the real PAT set out-of-band is not overwritten on the next `apply`.

## Related Modules

- [infrastructure/terraform/foundation/modules/iam](iam/CONTEXT.md) — Shares Authentication & Authorization domain (github oidc)
- [infrastructure/terraform/foundation/modules/iam](iam/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (github oidc)
- [infrastructure/terraform/foundation/modules/iam](iam/CONTEXT.md) — Shares CI/CD & Deployment Pipeline domain (github oidc)
