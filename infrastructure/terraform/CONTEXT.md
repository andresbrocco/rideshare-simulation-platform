# CONTEXT.md — Terraform

## Purpose

Provisions all AWS production infrastructure for the rideshare platform using a staged deployment model split into three independent Terraform roots: `bootstrap` (state backend), `foundation` (shared long-lived resources), and `platform` (compute and workloads). Each root has its own state file; `platform` reads `foundation` outputs via remote state.

## Responsibility Boundaries

- **Owns**: AWS resource lifecycle (VPC, EKS, RDS, S3 buckets, IAM roles, ACM certs, CloudFront, ECR, Glue catalog databases, KMS CMK, DynamoDB table, Lambda function, Secrets Manager secrets, SES domain identity, Route 53 zones and records)
- **Delegates to**: `infrastructure/kubernetes` for what runs on EKS; `infrastructure/lambda/auth-deploy` for the Lambda source code that this module packages and deploys
- **Does not handle**: Kubernetes manifests, Helm releases (those are in `infrastructure/kubernetes`), Docker image builds, or application configuration

## Key Concepts

**Three-root deployment sequence:**
1. `bootstrap` — creates the S3 bucket used as Terraform remote state backend (`rideshare-tf-state-<account-id>`). Must be applied once with local state before any other root.
2. `foundation` — long-lived shared resources: VPC, subnets, security groups, Route 53 zone, ACM certificate, S3 lakehouse buckets, ECR repositories, Secrets Manager secrets, IAM roles (both EKS cluster/node roles and per-workload Pod Identity roles), Glue catalog databases, KMS CMK (`rideshare-visitor-passwords`), DynamoDB table (`rideshare-visitors`), SES domain identity with DKIM/SPF/DMARC DNS records, and the `rideshare-auth-deploy` Lambda.
3. `platform` — compute resources that are destroyed between demo sessions: EKS cluster and managed node group, RDS PostgreSQL instance, ALB controller (via Helm), DNS records for the running platform.

**Remote state chaining:** `platform/data.tf` reads `foundation` outputs from S3 (`foundation/terraform.tfstate`) so EKS can reference the VPC, subnet IDs, and IAM role ARNs created by foundation without duplicating them.

**Backend config at init time:** The S3 backend bucket name includes the AWS account ID suffix, so it is not hardcoded in `backend.tf`. Both `foundation` and `platform` backends require `-backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"` at `terraform init`.

**Pod Identity (not IRSA):** All workload IAM roles trust `pods.eks.amazonaws.com` with `sts:AssumeRole` + `sts:TagSession`. Pod Identity associations are declared in `platform/main.tf` and bind (cluster, namespace, service_account) tuples to the roles defined in `foundation/modules/iam/eks_roles.tf`. No OIDC provider annotation on ServiceAccounts is required.

**Glue Job role separation:** Airflow's Pod Identity role cannot directly write to Silver/Gold — it passes the `rideshare-glue-job` role to Glue Interactive Sessions via `iam:PassRole`. The Glue job role trusts `glue.amazonaws.com`, not `pods.eks.amazonaws.com`.

**ACM must be us-east-1:** The ACM module uses a provider alias (`aws.us_east_1`) because CloudFront requires certificates in us-east-1 regardless of where other resources are deployed. The CloudFront alias A-record in Route 53 is created in `foundation/main.tf` (not inside the route53 module) to break the circular dependency: route53 zone → CloudFront → ACM → route53 validation record.

## Non-Obvious Details

- `platform.tfvars` sets `node_count = 3` but the EKS module default and cost-conscious default in `platform/variables.tf` is `1`. The tfvars value overrides for full-capacity demo runs; changing it back to `1` reduces cost to ~$0.31/hr.
- ESO (External Secrets Operator) also gets a node-level Secrets Manager policy on the EKS node role in addition to its Pod Identity role, because the ESO Pod Identity webhook may not be available during initial cluster bootstrap.
- The `rideshare-auth-deploy` Lambda uses `authorization_type = "NONE"` on its function URL — auth is implemented inside the function itself (API key + GitHub PAT validation), not at the AWS layer. Its timeout is 60 s (increased from 30 s) to accommodate SES send + DynamoDB write round-trips during visitor provisioning.
- Two Secrets Manager secrets are created at runtime by the Lambda, not by Terraform: `rideshare/trino-admin-password-hash` (written by the deploy workflow after the admin password is set) and `rideshare/trino-visitor-password-hash-*` (written on first visitor sign-up). These secrets do not exist in Terraform state — do not attempt to import or manage them here.
- `environments/prod/` holds `.tfvars` files that override module defaults for production. These are passed via `-var-file` at apply time; they are not automatically loaded.
- The `foundation` root creates Glue catalog databases (`rideshare_bronze`, `rideshare_silver`, `rideshare_gold`) but does not register tables — table registration is handled at runtime by the bronze-init CronJob.

## Related Modules

- [infrastructure/lambda/auth-deploy](../lambda/auth-deploy/CONTEXT.md) — Dependency — Control-plane Lambda for platform deploy/teardown lifecycle: API key auth, GitHu...
- [infrastructure/terraform/foundation](foundation/CONTEXT.md) — Shares CloudFront and DNS domain (acm us-east-1 provider alias)
