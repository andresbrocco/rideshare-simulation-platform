# CONTEXT.md — production-duckdb Overlay

## Purpose

Kustomize overlay that configures the full platform stack for production deployment when `DBT_RUNNER=duckdb` is selected. In this mode, Trino uses a self-hosted Hive Metastore (backed by RDS PostgreSQL) as its table catalog, rather than AWS Glue. This overlay is the ArgoCD deployment target for the DuckDB-runner variant of production.

## Responsibility Boundaries

- **Owns**: All patches and resource additions needed to run Hive Metastore in production (RDS backend, IRSA S3 access, removal of MinIO dependencies)
- **Delegates to**: `../../components/aws-production` for cross-overlay production concerns (image overrides, secrets, ingress, resource limits), `../../manifests/*` for base resource definitions
- **Does not handle**: Glue catalog configuration (that is `production-glue` overlay), local development configuration (that is `../../manifests/` used directly)

## Key Concepts

- **DBT_RUNNER=duckdb**: The platform supports two production catalog backends — Hive Metastore (this overlay) and AWS Glue (`production-glue` overlay). The DuckDB runner requires a local Hive Metastore because dbt-duckdb reads Delta tables via the Hive thrift protocol rather than the Glue API.
- **Hive Metastore over thrift**: Trino's Delta Lake connector points at `thrift://hive-metastore:9083`. The metastore itself stores table metadata in RDS PostgreSQL (`metastore` database) and routes S3 object access via the S3A filesystem.
- **IRSA credential chain**: Production has no MinIO and no static S3 credentials. Both Trino and Hive Metastore acquire S3 credentials via IRSA (IAM Roles for Service Accounts). The default AWS credential chain picks up the projected service account token automatically — no explicit `fs.s3a.access.key` or `fs.s3a.secret.key` is set.

## Non-Obvious Details

- **`SERVICE_OPTS` JVM property workaround**: Database credentials are passed to Hive Metastore as JVM system properties (`-Djavax.jdo.option.ConnectionPassword`) rather than embedded in `hive-site.xml`. This avoids two problems: (1) XML-special characters in RDS passwords (e.g., `&`, `<`) would break the XML parser if written directly into the config file; (2) Kubernetes `$(VAR)` expansion ordering is unreliable after Kustomize strategic merge patches. The container command builds `SERVICE_OPTS` at runtime from injected environment variables.
- **`wait-for-minio` initContainer deletion**: The base manifest includes a MinIO readiness gate that is meaningless in production. This overlay uses `$patch: delete` to remove it, replacing it with a readiness check against the RDS endpoint instead.
- **Placeholder substitution required at deploy time**: `<rds-endpoint>` and `<account-id>` appear literally in `hive-metastore-patch.yaml` and `hive-site-config-patch.yaml`. The CI/CD deploy workflow must substitute these with Terraform outputs before applying — they are not Kubernetes secret references or environment variable expansions.
- **`trino-glue-catalog.yaml` is included but overridden**: The base `trino-glue-catalog.yaml` manifest is listed under `resources` (to satisfy Kustomize resource graph completeness), but `trino-catalog-patch.yaml` replaces the catalog configuration with the Hive thrift URI, effectively neutralizing the Glue catalog for this overlay.
- **`delta.register-table-procedure.enabled=true`**: Required in production so that the bronze-init CronJob can register newly arrived Delta tables into the Hive Metastore at runtime, matching local dev behavior where tables are similarly registered on arrival.

## Related Modules

- [infrastructure/kubernetes/argocd](../../argocd/CONTEXT.md) — Reverse dependency — Provides app-rideshare-platform.yaml, install.yaml, sync-policy.yaml
- [infrastructure/kubernetes/components/aws-production](../../components/aws-production/CONTEXT.md) — Dependency — Reusable Kustomize Component bundling all AWS-specific production configuration ...
- [infrastructure/kubernetes/manifests](../../manifests/CONTEXT.md) — Dependency — Base Kubernetes manifests for all platform services, infrastructure dependencies...
- [infrastructure/kubernetes/overlays](../CONTEXT.md) — Shares Trino and Hive Metastore domain (hive metastore thrift catalog)
