# infrastructure/scripts

> Infrastructure bootstrap and operational scripts for secrets management, data pipeline validation, and DBT export

## Quick Reference

### Environment Variables

#### Secrets Management (seed-secrets.py, fetch-secrets.py)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AWS_ENDPOINT_URL` | LocalStack endpoint for Secrets Manager | None (uses AWS) | No |
| `AWS_ACCESS_KEY_ID` | AWS access key | `test` (LocalStack) | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `test` (LocalStack) | Yes |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` | No |
| `OVERRIDE_<KEY>` | Override individual secret values | None | No |
| `SECRETS_OUTPUT_DIR` | Output directory for env files | `/secrets` | No |

#### Data Pipeline (check_bronze_tables.py, export-dbt-to-s3.py)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AWS_ENDPOINT_URL` | MinIO S3 endpoint | `http://minio:9000` | No |
| `AWS_ACCESS_KEY_ID` | MinIO access key | `minioadmin` | No |
| `AWS_SECRET_ACCESS_KEY` | MinIO secret key | `minioadmin` | No |
| `AWS_REGION` | AWS region | `us-east-1` | No |
| `DUCKDB_PATH` | Path to DuckDB file | `/tmp/rideshare.duckdb` | No |
| `S3_ENDPOINT` | S3 endpoint for DBT export | `http://minio:9000` | No |

#### Trino Registration (register-delta-tables.sh)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TRINO_HOST` | Trino server hostname | `trino` | No |
| `TRINO_PORT` | Trino server port | `8080` | No |

### Commands

```bash
# Secrets Management
./venv/bin/python3 infrastructure/scripts/seed-secrets.py      # Seed LocalStack with credentials
./venv/bin/python3 infrastructure/scripts/fetch-secrets.py     # Fetch secrets to env files

# Data Pipeline Validation
./venv/bin/python3 infrastructure/scripts/check_bronze_tables.py   # Verify Bronze tables exist

# DBT Export (DuckDB → MinIO Delta Lake)
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py      # Export both silver and gold
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py --layer silver
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py --layer gold

# Trino Registration (runs as Docker init container)
bash infrastructure/scripts/register-delta-tables.sh
# Or manually:
docker exec rideshare-trino /bin/bash /opt/init-scripts/register-delta-tables.sh
```

### Configuration

All scripts read environment variables - no configuration files required.

### Prerequisites

- Python 3.11+ with virtual environment (`./venv/bin/python3`)
- boto3 (AWS SDK for Python)
- deltalake (delta-rs Python bindings)
- duckdb (for DBT export)
- LocalStack running at `http://localhost:4566` (for local development)
- MinIO running at `http://minio:9000` (for S3-compatible storage)
- Trino running at `http://trino:8080` (for Delta table registration)

## Common Tasks

### Bootstrap Secrets for Local Development

```bash
# Seed all credentials into LocalStack Secrets Manager
AWS_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py

# Fetch secrets and write to /secrets volume (runs automatically in Docker Compose)
./venv/bin/python3 infrastructure/scripts/fetch-secrets.py
```

### Override Default Credentials

```bash
# Change MinIO credentials from default admin/adminadmin
OVERRIDE_MINIO_ROOT_USER=myminio \
OVERRIDE_MINIO_ROOT_PASSWORD=mypassword \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

### Verify Bronze Layer Before DBT Run

```bash
# Check if all Bronze tables exist (used by Airflow DAGs)
./venv/bin/python3 infrastructure/scripts/check_bronze_tables.py

# Exit codes:
#   0 - All Bronze tables exist and have data
#   1 - One or more tables missing (skip DBT)
#   2 - Connection error to MinIO
```

### Export DBT Tables to Trino-Queryable Delta Lake

```bash
# Export DuckDB tables to MinIO as Delta tables
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py

# Export only silver layer
./venv/bin/python3 infrastructure/scripts/export-dbt-to-s3.py --layer silver

# Register exported tables in Trino catalog
docker compose -f infrastructure/docker/compose.yml restart delta-table-init
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `seed-secrets.py` fails with connection error | LocalStack not running | Start LocalStack: `docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d localstack` |
| `fetch-secrets.py` returns empty secrets | Secrets not seeded yet | Run `seed-secrets.py` first |
| `check_bronze_tables.py` exits with code 2 | MinIO not reachable | Check MinIO health: `curl http://localhost:9001/minio/health/live` |
| `check_bronze_tables.py` exits with code 1 | Bronze tables not created yet | Start simulation and bronze-ingestion: `docker compose --profile core --profile data-pipeline up -d` |
| `export-dbt-to-s3.py` fails with "DuckDB file not found" | DBT hasn't run yet | Run DBT first: `./venv/bin/dbt run` |
| `register-delta-tables.sh` shows "not found" warnings | Delta tables don't exist yet | Run bronze-ingestion or DBT export first |
| Trino tables missing after export | Tables not registered in Hive Metastore | Run `register-delta-tables.sh` or restart `delta-table-init` container |

## Script Details

### seed-secrets.py

**Purpose**: Populate LocalStack Secrets Manager with all project credentials
**Idempotent**: Yes - creates new secrets or updates existing ones
**Secrets Created**:
- `rideshare/api-key` - REST API and WebSocket authentication
- `rideshare/minio` - MinIO S3 credentials
- `rideshare/redis` - Redis AUTH password
- `rideshare/kafka` - Kafka SASL credentials
- `rideshare/schema-registry` - Schema Registry authentication
- `rideshare/postgres-airflow` - Airflow metadata DB
- `rideshare/postgres-metastore` - Hive Metastore DB
- `rideshare/airflow` - Airflow Fernet keys and admin credentials
- `rideshare/grafana` - Grafana admin credentials
- `rideshare/hive-thrift` - Hive LDAP credentials
- `rideshare/ldap` - OpenLDAP admin credentials

**Exit Codes**: 0 (success), 1 (failed to seed one or more secrets)

### fetch-secrets.py

**Purpose**: Fetch secrets from Secrets Manager and write grouped env files
**Idempotent**: Yes - overwrites env files with latest secret values
**Output Files**:
- `/secrets/core.env` - Simulation runtime services (API, Redis, Kafka, Schema Registry)
- `/secrets/data-pipeline.env` - ETL, ingestion, orchestration (MinIO, Airflow, Postgres, LDAP, Hive)
- `/secrets/monitoring.env` - Observability stack (Grafana)

**Exit Codes**: 0 (success), 1 (failed to fetch or write)

### check_bronze_tables.py

**Purpose**: Verify all required Bronze layer Delta tables exist before DBT run
**Idempotent**: Yes - safe to run repeatedly
**Required Tables**: 8 Bronze tables (trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles)
**Exit Codes**: 0 (all tables exist), 1 (tables missing), 2 (connection error)

### export-dbt-to-s3.py

**Purpose**: Export DBT DuckDB tables to MinIO as Delta Lake tables for Trino queries
**Idempotent**: Yes - overwrites existing Delta tables
**Layers Exported**: Silver (12 tables), Gold (14 tables)
**Exit Codes**: 0 (success), 1 (DuckDB file not found)

### register-delta-tables.sh

**Purpose**: Register Delta table locations in Hive Metastore via Trino
**Idempotent**: Yes - skips already-registered tables
**Tables Registered**: Bronze (16 tables including DLQ), Silver (12 tables), Gold (14 tables)
**Execution**: Runs automatically as Docker init container `delta-table-init`
**Exit Codes**: Always 0 (warnings for missing data are expected)

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and idempotency patterns
- [../docker/compose.yml](../docker/compose.yml) — Docker Compose secrets integration
- [../../CLAUDE.md](../../CLAUDE.md) — Project-wide secrets management overview
