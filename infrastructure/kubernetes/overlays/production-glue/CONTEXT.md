# CONTEXT.md — Production-Glue Overlay

## Purpose

Kustomize overlay for the `DBT_RUNNER=glue` production deployment variant. This overlay assembles the full platform without Hive Metastore or its associated RDS database, instead relying on AWS Glue Data Catalog as Trino's metastore backend. It is one of two mutually exclusive production targets (the other being `production-duckdb`).

## Responsibility Boundaries

- **Owns**: The complete Kubernetes resource set for the Glue-backed production environment, including Trino catalog configuration swap and Airflow environment injection
- **Delegates to**: `../../components/aws-production` for AWS-specific patches (IAM, node selectors, resource limits, etc.) and `../../manifests/*` for base resource definitions
- **Does not handle**: Hive Metastore deployment, MinIO (local object storage), or DuckDB-backed Trino catalog — those belong to `production-duckdb`

## Key Concepts

- **DBT_RUNNER=glue**: Controls which dbt profile Airflow uses. When set to `glue`, dbt submits transformation jobs to AWS Glue rather than running locally. Airflow webserver and scheduler both receive this env var.
- **Glue Data Catalog as Trino metastore**: Trino reads table metadata from AWS Glue instead of a Hive Metastore service. The `trino-config-glue` ConfigMap contains the catalog properties file with Glue connector configuration.
- **Strategic merge patch deletion**: `$patch: delete` in `trino-glue-catalog-patch.yaml` removes the `wait-for-hive-metastore` and `wait-for-minio` init containers from the base Trino Deployment, since neither dependency is present in this variant.

## Non-Obvious Details

- **Manual ARN substitution required**: The `GLUE_ROLE_ARN` value is set to the literal string `<glue-role-arn>` in the kustomization. Before deploying, this placeholder must be replaced with the actual Terraform output: `terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn`. Deploying with the placeholder value will cause dbt-glue profile failures at runtime.
- **Patch mutual exclusivity**: `trino-glue-catalog-patch.yaml` and `trino-catalog-patch.yaml` (used in `production-duckdb`) must never be applied simultaneously. Applying both patches to the same Trino Deployment will produce conflicting volume mounts and init container sequences.
- **Config source swap**: The patch rewrites the `config-source` volume to reference `trino-config-glue` ConfigMap and removes MinIO credential env vars from the `setup-config` init container, since S3 access in this variant uses IAM role via Pod Identity rather than static credentials.
- **No Hive-related resources**: Unlike `production-duckdb`, this overlay does not include `hive-metastore.yaml`, `postgres-metastore.yaml`, or `postgres-airflow.yaml` manifests.

## Related Modules

- [infrastructure/kubernetes/argocd](../../argocd/CONTEXT.md) — Reverse dependency — Provides app-rideshare-platform.yaml, install.yaml, sync-policy.yaml
- [infrastructure/kubernetes/components/aws-production](../../components/aws-production/CONTEXT.md) — Dependency — Reusable Kustomize Component bundling all AWS-specific production configuration ...
- [infrastructure/kubernetes/manifests](../../manifests/CONTEXT.md) — Dependency — Base Kubernetes manifests for all platform services, infrastructure dependencies...
