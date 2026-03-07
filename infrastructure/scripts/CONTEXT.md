# CONTEXT.md — Infrastructure Scripts

## Purpose

One-shot operational scripts that bootstrap, bridge, and gate the data platform at startup and between pipeline stages. These scripts are not application code — they run as init containers, Airflow tasks, or manual operator tools to wire together services that cannot discover each other automatically.

## Responsibility Boundaries

- **Owns**: Secrets seeding and fetching, Delta table catalog registration (Trino and Glue), DuckDB-to-S3 export, Bronze readiness gating, Lambda function deployment to LocalStack
- **Delegates to**: AWS Secrets Manager / LocalStack for secret storage, Trino REST API and Glue API for catalog operations, delta-rs (`deltalake` Python package) for Delta table I/O
- **Does not handle**: Data transformation, schema evolution, or ongoing service operations — each script is a bounded one-shot action

## Key Concepts

- **Secrets bootstrap flow**: `seed-secrets.py` populates four `rideshare/*` secret groups in Secrets Manager (LocalStack dev or real AWS). `fetch-secrets.py` reads those groups and writes grouped `.env` files (`core.env`, `data-pipeline.env`, `monitoring.env`) consumed by Docker Compose profiles. Airflow and Grafana keys are remapped during fetch (e.g., `FERNET_KEY` → `AIRFLOW__CORE__FERNET_KEY`, `ADMIN_USER` → `GF_SECURITY_ADMIN_USER`).
- **Dual-path table registration**: Delta tables written by `bronze-ingestion` (delta-rs) and DBT exports are not auto-discovered by query engines. Two registration scripts exist for different runtimes: `register-delta-tables.sh` (uses Trino CLI, runs in Docker init container) and `register-trino-tables.py` (uses Trino REST API, runs from Airflow which lacks the CLI). `register-glue-tables.py` handles AWS Glue Data Catalog for the production path using dbt-glue Interactive Sessions.
- **DuckDB-to-Delta bridge**: `export-dbt-to-s3.py` reads Silver/Gold DBT output from a DuckDB file and writes it to S3 as Delta tables via delta-rs. This step is required before Trino can query those tables. Empty tables are skipped to avoid creating empty Delta logs.
- **Bronze readiness gate**: `check_bronze_tables.py` is called by Airflow before DBT Silver transformations. It exits 1 (skip DBT run) if any of the 8 required Bronze Delta tables are absent from MinIO, and exits 2 on connectivity failure. Uses `DeltaTable.is_deltatable()` for fast existence checking without scanning data.

## Non-Obvious Details

- `register-trino-tables.py` parses `TRINO_PORT` defensively: Kubernetes auto-injects `TRINO_PORT=tcp://IP:PORT` for services named `trino`, so the script strips everything before the last `:` when the value starts with `tcp://`.
- `anomalies_gps_outliers` and `anomalies_zombie_drivers` are DBT views (not physical tables), so they have no `_delta_log` and are intentionally absent from `register-trino-tables.py`'s `SILVER_TABLES` list — adding them causes registration failures.
- `register-glue-tables.py` checks for the initial transaction log file (`_delta_log/00000000000000000000.json`) as a proxy for table existence before attempting Glue registration. Silver and Gold Glue registration is not yet implemented — `SILVER_TABLES` and `GOLD_TABLES` are empty lists.
- `export-dbt-to-s3.py` uses `AWS_S3_ALLOW_UNSAFE_RENAME=true` in storage options — required by delta-rs for S3-compatible stores that lack atomic rename (MinIO and S3 itself). Without this flag, Delta writes fail on commit.
- `seed-secrets.py` supports per-key override via `OVERRIDE_<KEY>` environment variables, allowing CI or deployment scripts to inject production values without editing the defaults.
- `deploy-lambda.py` uses a dummy IAM role ARN (`arn:aws:iam::000000000000:role/lambda-role`) because LocalStack accepts any syntactically valid ARN and does not enforce role trust policies.

## Related Modules

- [infrastructure/docker](../docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/kubernetes/components](../kubernetes/components/CONTEXT.md) — Reverse dependency — Provides aws-production component (kustomization.yaml)
- [infrastructure/kubernetes/components/aws-production](../kubernetes/components/aws-production/CONTEXT.md) — Reverse dependency — Provides ECR image references for all custom services, ServiceAccounts for IRSA/Pod Identity workloads, SecretStore aws-secrets-manager (+4 more)
