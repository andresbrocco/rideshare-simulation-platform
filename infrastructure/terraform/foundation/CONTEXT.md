# CONTEXT.md — Foundation

## Purpose

Provisions all AWS infrastructure that must exist before the EKS cluster is created — the "underpinning" layer. This includes networking (VPC), DNS (Route 53 + ACM), object storage (S3), container registry (ECR), secrets (Secrets Manager), IAM roles, Glue Data Catalog databases, and the auth/deploy Lambda. The platform Terraform layer depends on these outputs to deploy the Kubernetes workloads.

## Responsibility Boundaries

- **Owns**: VPC, subnets, security groups, Route 53 hosted zone, ACM certificate, S3 buckets (bronze/silver/gold/checkpoints/frontend/logs/loki/tempo/build_assets), ECR repositories, IAM roles for EKS/CI/workloads, Secrets Manager secrets, Glue catalog databases (bronze/silver/gold), EventBridge Scheduler role, Lambda `rideshare-auth-deploy`, Glue catalog databases for the medallion layers, and SES domain identity with DKIM/SPF/DMARC DNS records
- **Delegates to**: `infrastructure/terraform/platform` for EKS cluster, node groups, ALB, RDS, and DNS records pointing at the cluster
- **Does not handle**: Kubernetes manifests, application deployments, or runtime configuration

## Key Concepts

- **Two-layer Terraform split**: Foundation creates long-lived global resources (VPC, IAM, S3, DNS). Platform creates cluster-level resources that are torn down and recreated for cost control. This split allows the platform to be destroyed between sessions without losing DNS delegation, S3 data, or IAM roles.
- **DNS delegation chain**: A subdomain hosted zone (`ridesharing.portfolio.andresbrocco.com`) is created by the `route53` module. An NS delegation record in the parent zone (`andresbrocco.com`) is created directly in `main.tf` (not in the module) using the `enable_dns_delegation` toggle. The CloudFront apex alias record is also declared at the root level rather than inside the `route53` module to break a circular dependency: `route53 → cloudfront → acm → route53`.
- **ACM must be us-east-1**: CloudFront requires certificates in `us-east-1` regardless of the project region. A dedicated `aws.us_east_1` provider alias is defined in `versions.tf` and explicitly passed to the `acm` module.
- **S3 bucket naming**: Buckets include the AWS account ID suffix (`account_suffix = data.aws_caller_identity.current.account_id`) to guarantee global uniqueness without hardcoding account numbers.
- **Backend init pattern**: The S3 state backend omits the `bucket` argument; it is supplied at `terraform init` time via `-backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"` to avoid hardcoding account-specific values in source.
- **Lambda auth-deploy**: A Python 3.13 Lambda that validates API keys and triggers GitHub Actions deploys via EventBridge Scheduler. It is provisioned here (not in platform) because it must survive platform teardowns and expose a stable Function URL to the frontend.
- **Glue catalog databases**: Three Glue databases (bronze/silver/gold) are declared at the root level (not in a separate module) because they are thin `aws_glue_catalog_database` resources with no associated jobs or crawlers — they serve as the schema registry target for DBT/Trino in production.

## Non-Obvious Details

- The Route 53 alias record for CloudFront (`aws_route53_record.cloudfront_apex`) is intentionally declared in `main.tf` rather than inside the `route53` module. If it were inside the module, Terraform would create a circular dependency: the route53 module would need to reference CloudFront, which needs ACM, which needs the route53 zone ID.
- `enable_dns_delegation = false` is the safe default when running in an account where the parent zone does not exist. Setting it to `true` without the parent zone present causes a data source lookup failure at plan time.
- The EventBridge Scheduler execution role (`rideshare-scheduler-exec`) and its invoke policy are declared inline in `main.tf` rather than in the IAM module because they are tightly coupled to the specific Lambda ARN and needed before the Lambda module call.
- IAM workload roles (simulation, bronze-ingestion, airflow, trino, hive-metastore, loki, tempo, ESO, Glue) are created here without OIDC trust conditions — they use Pod Identity trust (`pods.eks.amazonaws.com`) configured in the platform layer.

## Related Modules

- [infrastructure/lambda/auth-deploy](../../lambda/auth-deploy/CONTEXT.md) — Dependency — Control-plane Lambda for platform deploy/teardown lifecycle: API key auth, GitHu...
- [infrastructure/terraform](../CONTEXT.md) — Shares CloudFront and DNS domain (acm us-east-1 provider alias)
- [infrastructure/terraform/environments](../environments/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/terraform/platform](../platform/CONTEXT.md) — Reverse dependency — Provides cluster_name, cluster_endpoint, cluster_ca_data (+6 more)
- [infrastructure/terraform/platform](../platform/CONTEXT.md) — Shares Terraform Infrastructure as Code domain (two-layer terraform split (foundation vs platform))
- [infrastructure/terraform/platform/modules](../platform/modules/CONTEXT.md) — Reverse dependency — Provides cluster_id, cluster_name, cluster_endpoint (+7 more)
