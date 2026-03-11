# CONTEXT.md — Environments

## Purpose

Holds environment-specific Terraform variable overrides (`.tfvars` files) that parameterize the `foundation` and `platform` root modules for a given deployment target. Currently contains only the `prod` environment.

## Responsibility Boundaries

- **Owns**: Concrete variable values for each named environment (region, domain, cluster sizing, instance types)
- **Delegates to**: `infrastructure/terraform/foundation` and `infrastructure/terraform/platform` for all resource definitions and module logic
- **Does not handle**: Module source definitions, resource declarations, or backend configuration

## Key Concepts

The environment directory mirrors the two-layer deployment order:
- `foundation.tfvars` — applied when deploying `terraform/foundation` (VPC, ACM, IAM, Route53, S3, Secrets Manager, GitHub OIDC, KMS, DynamoDB, SES)
- `platform.tfvars` — applied when deploying `terraform/platform` (EKS, RDS, ALB, DNS)

Both files must share the same `aws_region`, `project_name`, and `domain_name` values to keep the two layers consistent.

## Non-Obvious Details

- `platform.tfvars` specifies `node_count = 3`, but the platform was optimized to run on a single `t3.xlarge` node (`node_count = 1`) to reduce cost (~$0.31/hr vs ~$0.65/hr). The file may reflect an outdated default — verify before deploying.
- The production domain is `ridesharing.portfolio.andresbrocco.com` (not `rideshare.andresbrocco.com`). All ACM certificates, Route53 records, and Kubernetes ingress hostnames derive from this value.
- `foundation.tfvars` includes `github_org`, `github_repo`, and `github_branch` used to configure the GitHub OIDC trust for CI/CD IAM roles. The branch is `main`.
- `foundation.tfvars` must include `owner_reply_to_email` — a sensitive, required variable (no default) that sets the `Reply-To` address on visitor welcome emails sent via SES. It is declared `sensitive = true` in variables.tf and will not appear in `terraform plan` output. If this value is omitted, `terraform plan` will prompt interactively and CI/CD pipelines will fail. It must be supplied via `-var` flag or a `secrets.tfvars` file excluded from version control.

## Related Modules

- [infrastructure/terraform/foundation](../foundation/CONTEXT.md) — Dependency — Provisions long-lived AWS infrastructure that must exist before the EKS cluster ...
- [infrastructure/terraform/platform](../platform/CONTEXT.md) — Dependency — Runtime infrastructure layer — EKS cluster, RDS, ALB controller, External Secret...
