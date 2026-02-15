# CONTEXT.md — Infrastructure Scripts

## Purpose

Bootstrap and operational scripts for infrastructure initialization tasks that run outside the main service containers. Handles secrets management (seeding/fetching from AWS Secrets Manager), data pipeline readiness validation (Bronze table checks), and DBT-to-S3 export bridging between DuckDB transformations and Trino queries.

## Responsibility Boundaries

- **Owns**: Secret seeding/retrieval from AWS Secrets Manager, Bronze layer existence validation before DBT runs, DBT table export from DuckDB to S3 Delta format, Hive Metastore table registration via Trino
- **Delegates to**: AWS Secrets Manager for credential storage, MinIO for S3-compatible storage, Trino for table registration procedures, DuckDB for local DBT state
- **Does not handle**: Service-level business logic, container orchestration, credential generation policies, data transformations themselves

## Key Concepts

**Idempotent Operations**: All scripts support repeated execution without side effects. `seed-secrets.py` uses upsert pattern (create or update), `register-delta-tables.sh` checks existing registrations before creating, and table checks gracefully handle missing data.

**Profile-Grouped Secrets**: Secrets are fetched from AWS Secrets Manager and written to profile-specific env files (`core.env`, `data-pipeline.env`, `monitoring.env`) to limit credential exposure. Each profile's services only receive credentials they need.

**Key Transformation**: `fetch-secrets.py` applies transformations to avoid environment variable collisions. Generic keys like `POSTGRES_USER` become `POSTGRES_AIRFLOW_USER` or `POSTGRES_METASTORE_USER` when multiple secrets in the same profile have identical key names. Airflow secrets use double-underscore notation (`AIRFLOW__CORE__FERNET_KEY`).

**DuckDB-to-Trino Bridge**: The `export-dbt-to-s3.py` script enables local DBT development with DuckDB while maintaining production compatibility with Trino. It converts DuckDB tables to Delta format in S3, which Trino can query via Hive Metastore.

**LocalStack Migration Path**: All secrets scripts work identically with LocalStack (local development) and AWS Secrets Manager (production) by changing only the `AWS_ENDPOINT_URL` environment variable. No code changes required for production promotion.

## Non-Obvious Details

**Override Pattern**: `seed-secrets.py` supports `OVERRIDE_<KEY>` environment variables to replace individual secret values without modifying the script. For example, `OVERRIDE_MINIO_ROOT_USER=custom` replaces the default MinIO admin username.

**Airflow Cryptographic Keys**: Default Airflow secrets use deterministic base64-encoded values for local development consistency (not production-secure). Fernet keys are padded to exactly 32 bytes and URL-safe base64 encoded to meet Airflow's validation requirements.

**Bronze Table Check Exit Codes**: `check_bronze_tables.py` uses distinct exit codes for different failure modes: 0 (all tables ready), 1 (tables missing, skip DBT run), 2 (MinIO connection error). This allows Airflow DAGs to differentiate between retriable infrastructure failures and normal "data not ready yet" states.

**Delta Table Registration Timing**: `register-delta-tables.sh` expects Delta `_delta_log` directories to exist at S3 locations. It logs warnings for missing tables but doesn't fail, allowing it to run before bronze ingestion completes. Re-running the script after data arrives completes registration.

**Arrow Table Export**: `export-dbt-to-s3.py` uses DuckDB's Arrow integration to efficiently transfer large result sets to Delta format without intermediate serialization. Storage options include `AWS_S3_ALLOW_UNSAFE_RENAME` for LocalStack compatibility.

## Related Modules

- **[infrastructure/docker](../docker/CONTEXT.md)** — Docker Compose uses secrets-init service that runs these scripts to populate credentials before starting application services
- **[infrastructure/kubernetes](../kubernetes/CONTEXT.md)** — Kubernetes External Secrets Operator syncs from the same LocalStack Secrets Manager that these scripts populate
- **[services/airflow](../../services/airflow/CONTEXT.md)** — Airflow Silver DAG has its own inline Bronze readiness check via ShortCircuitOperator; check_bronze_tables.py remains available as a standalone CLI diagnostic tool
- **[tools/dbt](../../tools/dbt/CONTEXT.md)** — DBT Gold layer tables are exported to S3 via export-dbt-to-s3.py for Trino/Grafana querying
