# CONTEXT.md — IAM

## Purpose

Defines all AWS IAM roles and policies required to run the rideshare platform: CI/CD authentication via GitHub OIDC, EKS cluster and node roles, per-workload Pod Identity roles for least-privilege S3/Glue access, and a Glue job execution role passed by Airflow at runtime.

## Responsibility Boundaries

- **Owns**: Every IAM role and inline policy in the platform; the GitHub OIDC provider resource
- **Delegates to**: The platform Terraform layer (`infrastructure/terraform/platform/`) to create the Pod Identity associations that bind these roles to specific Kubernetes service accounts
- **Does not handle**: S3 bucket creation, Secrets Manager secret creation, EKS cluster creation — those are in sibling foundation modules or the platform layer

## Key Concepts

- **GitHub OIDC**: CI workflows assume `github_actions` via `sts:AssumeRoleWithWebIdentity` (not static access keys). Trust is scoped to a specific org/repo/branch.
- **EKS Pod Identity**: Workload roles (simulation, bronze-ingestion, airflow, trino, hive-metastore, loki, tempo, eso) trust `pods.eks.amazonaws.com` with both `sts:AssumeRole` and `sts:TagSession`. The actual binding to a Kubernetes service account is done via `aws_eks_pod_identity_association` resources in the platform layer, not here.
- **Glue two-role delegation**: Airflow holds a Pod Identity role (`airflow`) that can call `iam:PassRole` to hand off `glue_job` to Glue Interactive Sessions. `glue_job` trusts `glue.amazonaws.com`, not EKS — it is never assumed directly by a pod.

## Non-Obvious Details

- **ESO uses the node role, not Pod Identity**: `eks_nodes_secrets_manager` grants Secrets Manager read to the EC2 node instance role rather than creating a dedicated ESO Pod Identity role. The comment in `eks_roles.tf` explains this is intentional — the EKS Pod Identity webhook may not be available during initial cluster bootstrap, so ESO must work before it is installed.
- **Secrets Manager is scoped to `{project_name}/*`**: Both the node-role policy and the ESO policy restrict access to secrets prefixed with the project name, not the entire account.
- **Airflow needs `iam:PassRole`**: The `airflow_glue_sessions` policy includes a `PassGlueJobRole` statement with a condition `iam:PassedToService = glue.amazonaws.com`. Without this, Airflow cannot start Glue Interactive Sessions even if it has all other Glue permissions.
- **GitHub Actions branch scoping**: The OIDC trust condition uses `StringLike` on the `sub` claim, allowing only the configured branch (default `main`) to assume the CI role. Feature branches cannot assume it without changing the variable.
- **Terraform state locking**: The `github_actions_terraform` policy grants S3 CRUD on the `tf_state` bucket. Locking is done via S3-native `.tflock` files (not DynamoDB).
- **GitHub Actions Glue Catalog access**: The `github_actions_glue` policy grants `glue:GetDatabase`, `glue:GetDatabases`, `glue:GetTables`, and `glue:DeleteTable` scoped to `rideshare_*` databases and tables. This supports two CI workflows: the deploy health check (reads catalog to verify tables are registered) and `soft-reset.yml` (deletes Glue table entries as part of lakehouse cleanup). This is distinct from the Airflow `airflow_glue_sessions` policy — the CI role operates on the catalog directly, not via Glue Interactive Sessions.

## Related Modules

- [infrastructure/kubernetes/components](../../../../kubernetes/components/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/kubernetes/components](../../../../kubernetes/components/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/kubernetes/components/aws-production](../../../../kubernetes/components/aws-production/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/kubernetes/components/aws-production](../../../../kubernetes/components/aws-production/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/terraform/foundation/modules](../CONTEXT.md) — Shares Authentication & Authorization domain (github oidc)
- [infrastructure/terraform/foundation/modules](../CONTEXT.md) — Shares AWS Infrastructure & IAM domain (github oidc)
- [infrastructure/terraform/foundation/modules](../CONTEXT.md) — Shares CI/CD & Deployment Pipeline domain (github oidc)
- [infrastructure/terraform/platform/modules/alb](../../../platform/modules/alb/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](../../../platform/modules/alb/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
