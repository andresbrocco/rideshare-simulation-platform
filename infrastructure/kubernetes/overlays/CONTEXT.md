# CONTEXT.md — Overlays

## Purpose

Kustomize overlays that produce two mutually exclusive production deployment targets, differentiated by the DBT runner used for Silver/Gold transformations. Each overlay composes the base manifests and the shared `aws-production` component into a complete, ArgoCD-deployable configuration for `namespace: rideshare-prod`.

## Responsibility Boundaries

- **Owns**: Selecting which overlays/resources to include per runner variant, applying production-specific patches (swap MinIO for AWS S3/IRSA, target RDS endpoints, inject runner-specific env vars)
- **Delegates to**: `../../manifests/` for base resource definitions, `../../components/aws-production` for shared AWS production overrides (image tags, secrets, IAM service accounts)
- **Does not handle**: Terraform infrastructure provisioning, ArgoCD application definitions, CI/CD workflows that trigger deploys

## Key Concepts

**DBT_RUNNER variants** — The two overlays exist because the data transformation layer supports two catalog backends:
- `production-duckdb`: Uses a self-hosted Hive Metastore (thrift at port 9083) backed by RDS PostgreSQL. Deploys `hive-metastore` and `postgres-metastore` pods. Trino connects via `hive.metastore.uri=thrift://hive-metastore:9083`.
- `production-glue`: Uses AWS Glue Data Catalog as the Hive Metastore replacement. No Hive Metastore pod or RDS metastore DB. Trino uses `trino-config-glue` ConfigMap instead of `trino-config`.

**IRSA credential substitution** — Both overlays strip MinIO-specific credentials (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `fs.s3a.endpoint`) from the base manifests. AWS credentials are provided automatically at runtime via IRSA (projected service account tokens), so static keys are not present in the Kubernetes configs.

**Placeholder substitution** — Several files contain `<rds-endpoint>`, `<account-id>`, `<image-tag>`, and `<glue-role-arn>` tokens that must be replaced with Terraform outputs before deploy. These are not injected automatically.

## Non-Obvious Details

- The `production-duckdb` overlay passes RDS credentials to Hive Metastore via a runtime `bash -c` command that builds `SERVICE_OPTS` JVM properties at container startup. This bypasses two issues: Kubernetes `$(VAR)` expansion ordering after Kustomize merge, and XML-special characters in passwords that would break `hive-site.xml` if substituted statically.
- The `trino-glue-catalog-patch.yaml` in `production-glue` also deletes the `wait-for-hive-metastore` and `wait-for-minio` initContainers from the Trino Deployment. Applying both the duckdb and glue Trino patches simultaneously would produce conflicting catalog configurations and must be avoided.
- Airflow Deployments in `production-glue` receive `DBT_RUNNER=glue` and `GLUE_ROLE_ARN` env vars injected inline as strategic merge patches. The `<glue-role-arn>` value comes from `terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn`.
- `delta.register-table-procedure.enabled=true` is set in the duckdb overlay's Trino catalog patch, enabling the `register_table` stored procedure used by the bronze-init job to register Delta tables at runtime.

## Related Modules

- [infrastructure/kubernetes/components](../components/CONTEXT.md) — Reverse dependency — Provides aws-production component (kustomization.yaml)
- [infrastructure/kubernetes/components/aws-production](../components/aws-production/CONTEXT.md) — Dependency — Reusable Kustomize Component bundling all AWS-specific production configuration ...
- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Dependency — Base Kubernetes manifests for all platform services, infrastructure dependencies...
- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Reverse dependency — Provides All Deployment, Service, ConfigMap, Secret, PV, PVC, CronJob, HTTPRoute, Gateway, GatewayClass, StorageClass, ExternalSecret resources
- [infrastructure/kubernetes/overlays/production-duckdb](production-duckdb/CONTEXT.md) — Shares Trino and Hive Metastore domain (hive metastore thrift catalog)
