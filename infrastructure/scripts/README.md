# infrastructure/scripts

> One-shot operational scripts that bootstrap secrets, register Delta tables in catalog services, export DBT output to S3, and gate pipeline stages.

## Quick Reference

### Environment Variables

| Variable | Default | Used By | Purpose |
|---|---|---|---|
| `AWS_ENDPOINT_URL` | _(none)_ | All scripts | LocalStack endpoint (e.g. `http://localhost:4566`). Omit to target real AWS. |
| `AWS_ACCESS_KEY_ID` | `test` / `minioadmin` | All scripts | AWS or MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | `test` / `minioadmin` | All scripts | AWS or MinIO secret key |
| `AWS_DEFAULT_REGION` | `us-east-1` | `seed-secrets.py`, `fetch-secrets.py`, `deploy-lambda.py` | AWS region |
| `AWS_REGION` | `us-east-1` | `export-dbt-to-s3.py`, `register-glue-tables.py` | AWS region |
| `SECRETS_OUTPUT_DIR` | `/secrets` | `fetch-secrets.py` | Directory where grouped `.env` files are written |
| `TRINO_HOST` | `trino` | `register-trino-tables.py`, `register-delta-tables.sh` | Trino service hostname |
| `TRINO_PORT` | `8080` | `register-trino-tables.py`, `register-delta-tables.sh` | Trino service port |
| `BRONZE_BUCKET` | `rideshare-bronze` | `register-trino-tables.py`, `register-glue-tables.py` | S3/MinIO bucket for Bronze layer |
| `SILVER_BUCKET` | `rideshare-silver` | `register-trino-tables.py`, `export-dbt-to-s3.py` | S3/MinIO bucket for Silver layer |
| `GOLD_BUCKET` | `rideshare-gold` | `register-trino-tables.py`, `export-dbt-to-s3.py` | S3/MinIO bucket for Gold layer |
| `S3_ENDPOINT` | _(none)_ | `export-dbt-to-s3.py` | MinIO endpoint for local dev (falls back to `AWS_ENDPOINT_URL`) |
| `DUCKDB_PATH` | `/tmp/rideshare.duckdb` | `export-dbt-to-s3.py` | Path to DuckDB file containing DBT output tables |
| `OVERRIDE_<KEY>` | _(none)_ | `seed-secrets.py` | Override any individual secret value (e.g. `OVERRIDE_MINIO_ROOT_USER=myminio`) |

### Commands

**Seed secrets into LocalStack (run once at stack startup):**
```bash
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

**Fetch secrets from Secrets Manager and write Docker Compose env files:**
```bash
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/fetch-secrets.py
# Writes: /secrets/core.env, /secrets/data-pipeline.env, /secrets/monitoring.env
```

**Check Bronze layer readiness before running DBT:**
```bash
AWS_ENDPOINT_URL=http://minio:9000 \
./venv/bin/python3 infrastructure/scripts/check_bronze_tables.py
# Exit 0 = ready, 1 = tables missing, 2 = cannot reach MinIO
```

**Export DBT Silver/Gold tables from DuckDB to S3 as Delta tables:**
```bash
# Export both layers
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py

# Export only silver
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py --layer silver

# Export only gold
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py --layer gold
```

**Register Delta tables in Trino via REST API (used inside Airflow container):**
```bash
./venv/bin/python3 infrastructure/scripts/register-trino-tables.py --layer bronze
./venv/bin/python3 infrastructure/scripts/register-trino-tables.py --layer silver
./venv/bin/python3 infrastructure/scripts/register-trino-tables.py --layer gold
```

**Register Delta tables in Trino via CLI (Docker init container):**
```bash
# Runs automatically as a one-shot init container.
# To re-run manually:
docker exec rideshare-trino /bin/bash /opt/init-scripts/register-delta-tables.sh
```

**Register Delta tables in AWS Glue Data Catalog (production path):**
```bash
./venv/bin/python3 infrastructure/scripts/register-glue-tables.py --layer bronze
./venv/bin/python3 infrastructure/scripts/register-glue-tables.py --layer silver
./venv/bin/python3 infrastructure/scripts/register-glue-tables.py --layer gold
```

**Deploy auth Lambda to LocalStack:**
```bash
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/deploy-lambda.py
```

### Secret Groups

These secrets are seeded by `seed-secrets.py` and fetched by `fetch-secrets.py`:

| Secret Name | Keys Stored | Written To |
|---|---|---|
| `rideshare/api-key` | `API_KEY` | `core.env` |
| `rideshare/core` | `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `REDIS_PASSWORD`, `SCHEMA_REGISTRY_USER`, `SCHEMA_REGISTRY_PASSWORD` | `core.env` |
| `rideshare/data-pipeline` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `POSTGRES_AIRFLOW_*`, `POSTGRES_METASTORE_*`, Airflow crypto keys, `ADMIN_USERNAME/PASSWORD` | `data-pipeline.env` |
| `rideshare/monitoring` | `ADMIN_USER`, `ADMIN_PASSWORD` (becomes `GF_SECURITY_*`) | `monitoring.env` |
| `rideshare/github-pat` | `GITHUB_PAT` | _(not written to env files)_ |

### Delta Table Inventory

**Bronze layer** (`rideshare-bronze` bucket, `delta.bronze` schema):
- `bronze_trips`, `bronze_gps_pings`, `bronze_driver_status`, `bronze_surge_updates`, `bronze_ratings`, `bronze_payments`, `bronze_driver_profiles`, `bronze_rider_profiles`
- DLQ: `dlq_bronze_*` (mirrors above with `_error_message`, `_error_timestamp` columns)

**Silver layer** (`rideshare-silver` bucket, `delta.silver` schema):
- `stg_trips`, `stg_gps_pings`, `stg_driver_status`, `stg_surge_updates`, `stg_ratings`, `stg_payments`, `stg_drivers`, `stg_riders`, `anomalies_all`, `anomalies_impossible_speeds`
- Note: `anomalies_gps_outliers` and `anomalies_zombie_drivers` are DBT views (no Delta log) — they cannot be registered.

**Gold layer** (`rideshare-gold` bucket, `delta.gold` schema):
- Facts: `fact_trips`, `fact_payments`, `fact_ratings`, `fact_cancellations`, `fact_offers`, `fact_driver_activity`
- Dimensions: `dim_drivers`, `dim_riders`, `dim_zones`, `dim_time`, `dim_payment_methods`
- Aggregates: `agg_hourly_zone_demand`, `agg_daily_driver_performance`, `agg_daily_platform_revenue`, `agg_surge_history`

## Common Tasks

### Bootstrap a fresh local stack

1. Start LocalStack (part of the `core` Docker Compose profile).
2. Seed secrets:
   ```bash
   AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
   ./venv/bin/python3 infrastructure/scripts/seed-secrets.py
   ```
3. Fetch secrets to env files consumed by Docker Compose:
   ```bash
   AWS_ENDPOINT_URL=http://localhost:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
   ./venv/bin/python3 infrastructure/scripts/fetch-secrets.py
   ```

### Re-register Trino tables after restart

The `register-delta-tables.sh` script runs automatically as a Docker init container. If tables become unregistered:
```bash
docker compose -f infrastructure/docker/compose.yml restart delta-table-init
```

Or use the Python equivalent (works without the Trino CLI):
```bash
TRINO_HOST=localhost TRINO_PORT=8084 \
./venv/bin/python3 infrastructure/scripts/register-trino-tables.py --layer bronze
```

### Force-export DBT output after a pipeline run

```bash
# Local dev (MinIO)
S3_ENDPOINT=http://localhost:9000 \
AWS_ACCESS_KEY_ID=admin \
AWS_SECRET_ACCESS_KEY=adminadmin \
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py
```

### Override a secret value at seed time

Use `OVERRIDE_<KEY>` to inject a non-default value for any secret field:
```bash
OVERRIDE_API_KEY=mysecretkey \
AWS_ENDPOINT_URL=http://localhost:4566 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

## Troubleshooting

**`seed-secrets.py` fails with `ResourceExistsException` loop** — This should not happen; the script handles it by calling `update_secret`. If it persists, check that `AWS_ENDPOINT_URL` is pointing to the correct LocalStack instance.

**`fetch-secrets.py` fails with `SecretId not found`** — Run `seed-secrets.py` first. Secrets must exist before they can be fetched.

**`register-trino-tables.py` reports `[SKIP] ... no data in S3 yet`** — Normal for `stg_ratings` and `stg_payments` early in a run. Trips must complete before those tables populate. Re-run after DBT has processed completed trips.

**`check_bronze_tables.py` exits with code 2** — MinIO is unreachable. Ensure the `data-pipeline` Docker Compose profile is running and MinIO health endpoint responds at the configured `AWS_ENDPOINT_URL`.

**`export-dbt-to-s3.py` reports `ERROR: DuckDB file not found`** — DBT has not run yet, or `DUCKDB_PATH` is misconfigured. The default path is `/tmp/rideshare.duckdb` (inside the Airflow container).

**Trino `TRINO_PORT` receives `tcp://IP:PORT` format** — Normal on Kubernetes where the auto-injected env var includes the full service URL. `register-trino-tables.py` handles this automatically by extracting the numeric port from the string.

**`deploy-lambda.py` warns `AWS_ENDPOINT_URL not set — targeting real AWS Lambda`** — This is expected only in production. Always set `AWS_ENDPOINT_URL` for local development.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this scripts directory
- [infrastructure/docker/README.md](../docker/README.md) — Docker Compose profiles and service definitions
- [infrastructure/kubernetes/scripts/README.md](../kubernetes/scripts/README.md) — Kubernetes-specific operational scripts
- [services/bronze-ingestion/README.md](../../services/bronze-ingestion/README.md) — Bronze ingestion service that writes tables these scripts register
- [tools/dbt/README.md](../../tools/dbt/README.md) — DBT project whose output `export-dbt-to-s3.py` exports
