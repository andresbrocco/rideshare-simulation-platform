# CONTEXT.md — Infrastructure

## Purpose

Defines and provisions all platform infrastructure for both local development (Docker Compose) and production (AWS via Terraform). It also contains operational scripts that bridge the gap between infrastructure provisioning and runtime platform state — including secret seeding, Delta table registration in Trino and Glue, and the Lambda function that gates on-demand cluster deployments.

## Responsibility Boundaries

- **Owns**: Docker Compose configurations for local multi-service orchestration; Terraform modules for AWS resources (VPC, EKS, RDS, S3, ECR, CloudFront, Lambda, IAM, Glue catalog, Secrets Manager, KMS, DynamoDB, SES); Kubernetes manifests for production workloads; operational scripts for post-deploy registration and secret management; the Terraform Lambda module that deploys `services/auth-deploy`; IAM-compatible policy documents (`infrastructure/policies/`)
- **Delegates to**: Application services for their own runtime logic; `tools/dbt` and `services/airflow` for lakehouse transformations; CI/CD workflows (`.github/workflows`) for orchestrating Terraform apply and Kubernetes deploy sequences
- **Does not handle**: Application-level configuration (owned by each service's `config.py` or environment); Kafka topic schema definitions (owned by `schemas/`); monitoring dashboard content (owned by `services/grafana/`)

## Key Concepts

**Two-layer Terraform split — foundation vs. platform**: Foundation (`terraform/foundation`) provisions long-lived, cost-free-at-rest resources (VPC, S3 buckets, ECR, IAM roles, Glue catalog databases, Secrets Manager, ACM cert, CloudFront, Route 53 zone, Lambda). Platform (`terraform/platform`) provisions cost-incurring compute resources (EKS cluster and node group, RDS) that are created on deploy and destroyed on teardown. The two layers reference each other via `terraform_remote_state` — platform reads VPC subnets, security group IDs, and IAM role ARNs from foundation outputs.

**Bootstrap layer**: `terraform/bootstrap` is a one-time prerequisite that creates the S3 bucket used as Terraform remote state backend for both foundation and platform.

**EKS Pod Identity (not IRSA)**: All workload IAM roles trust `pods.eks.amazonaws.com` with `sts:AssumeRole` + `sts:TagSession`. Pod Identity associations are declared in `platform/main.tf` and matched by `(cluster, namespace, service_account)` — no OIDC annotation on the ServiceAccount is required. This is newer than IRSA and has no intermediate OIDC provider configuration.

**auth-deploy Lambda**: A Python 3.13 Lambda (`services/auth-deploy/handler.py`) that validates an API key from Secrets Manager, then triggers the GitHub Actions `deploy-platform.yml` or `teardown-platform.yml` workflow via the GitHub API. It also manages an EventBridge Scheduler for auto-teardown and uses SSM Parameter Store (`/rideshare/session/deadline`) to track session state. The Lambda is invoked by the frontend control panel, gating on-demand cluster lifecycle from the browser. It additionally handles **two-phase visitor provisioning**: Phase 1 (`provision-visitor`) stores durable visitor credentials in DynamoDB (KMS-encrypted plaintext password) and dispatches a SES welcome email — all before the platform is deployed. Phase 2 (`reprovision-visitors`) is called post-deploy to create ephemeral service accounts in Grafana, Airflow, MinIO, and the Simulation API by decrypting passwords from DynamoDB via KMS.

**Secret groups**: All credentials are stored as JSON objects under `rideshare/*` in Secrets Manager. `infrastructure/scripts/seed-secrets.py` populates LocalStack for local development. Secret group names: `rideshare/api-key`, `rideshare/core`, `rideshare/data-pipeline`, `rideshare/monitoring`, `rideshare/github-pat`.

**Delta table registration scripts**: Delta Lake tables written to S3 by bronze-ingestion are not automatically discoverable by Trino or Glue. `register-trino-tables.py` calls `delta.system.register_table()` via the Trino REST API. `register-glue-tables.py` creates Glue catalog entries via `boto3`. Both are run post-deploy as part of the Airflow DAG or CI pipeline.

**Glue Catalog databases**: Three Glue databases (`rideshare_bronze`, `rideshare_silver`, `rideshare_gold`) are created in the foundation layer and correspond to the medallion architecture tiers.

## Non-Obvious Details

- The Route 53 alias record for CloudFront is declared directly in `foundation/main.tf` (not in the `route53` module) to break a circular dependency: `route53 → cloudfront → acm → route53`. The zone is created by the module; the alias record is declared after both zone and CloudFront distribution exist.
- ACM certificates must be provisioned in `us-east-1` regardless of the deployment region, because CloudFront requires it. Foundation uses a provider alias (`aws.us_east_1`) for the `acm` module.
- `register-trino-tables.py` defensively strips a `tcp://IP:PORT` prefix from `TRINO_PORT` because Kubernetes auto-injects the full service URL into environment variables named after services (e.g., `TRINO_PORT=tcp://10.0.0.1:8080`). Without this stripping, Trino connection URLs would be malformed.
- DBT views (`materialized='view'`) have no physical Delta transaction log and cannot be registered as Trino Delta tables. `anomalies_gps_outliers` and `anomalies_zombie_drivers` are excluded from `SILVER_TABLES` in `register-trino-tables.py` for this reason.
- The GitHub Actions IAM role uses OIDC web identity federation restricted to a specific branch (`refs/heads/main`). Only pushes or workflow dispatches on `main` can assume the role.
- `seed-secrets.py` supports `OVERRIDE_<KEY>` environment variables to replace any individual secret value without editing the script, enabling CI to inject real credentials at seed time.
