# Airflow

> Orchestrates data lakehouse pipeline by scheduling DBT transformations, monitoring DLQ tables, and maintaining Delta Lake files

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_AIRFLOW_USER` | PostgreSQL database username | `admin` | Yes |
| `POSTGRES_AIRFLOW_PASSWORD` | PostgreSQL database password | `admin` | Yes |
| `AIRFLOW_ADMIN_USERNAME` | Airflow web UI admin username | `admin` | Yes |
| `AIRFLOW_ADMIN_PASSWORD` | Airflow web UI admin password | `admin` | Yes |
| `MINIO_ROOT_USER` | MinIO S3 access key | `admin` | Yes |
| `MINIO_ROOT_PASSWORD` | MinIO S3 secret key | `admin` | Yes |
| `PROD_MODE` | Enable production mode (limits Gold DAG to 2 AM only) | `false` | No |

### Airflow Web UI

| Component | URL | Description |
|-----------|-----|-------------|
| Web UI | http://localhost:8082 | DAG monitoring, task logs, manual triggers |
| Health Check | http://localhost:8082/api/v2/monitor/health | Service health endpoint |

**Default credentials:** admin/admin (configurable via `AIRFLOW_ADMIN_USERNAME`/`AIRFLOW_ADMIN_PASSWORD`)

### DAGs

| DAG ID | Schedule | Description | Profile |
|--------|----------|-------------|---------|
| `dbt_silver_transformation` | `10 * * * *` (hourly at :10) | Transforms Bronze → Silver via DBT | data-pipeline |
| `dbt_gold_transformation` | None (triggered by Silver DAG at 2 AM) | Transforms Silver → Gold (dimensions, facts, aggregates) | data-pipeline |
| `dlq_monitoring` | `3,18,33,48 * * * *` (every 15 minutes) | Monitors DLQ tables for errors via DuckDB | data-pipeline |
| `delta_maintenance` | `0 3 * * *` (3 AM daily) | Runs OPTIMIZE and VACUUM on Bronze Delta tables | data-pipeline |

### Docker Services

```bash
# Start Airflow (requires data-pipeline profile)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# View webserver logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-webserver

# View scheduler logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-scheduler

# Check health
curl http://localhost:8082/api/v2/monitor/health
```

### Configuration

| File | Purpose |
|------|---------|
| `dags/dbt_transformation_dag.py` | DBT Silver and Gold transformation pipelines |
| `dags/dlq_monitoring_dag.py` | DuckDB-based DLQ error monitoring |
| `dags/delta_maintenance_dag.py` | Delta Lake OPTIMIZE/VACUUM maintenance |
| `config/` | Airflow configuration overrides (if needed) |
| `plugins/` | Custom Airflow plugins (currently empty) |

### Database Tables

Airflow uses PostgreSQL (`postgres-airflow`) for metadata storage:

| Database | Port | Purpose |
|----------|------|---------|
| `postgres-airflow:5432` | 5432 | Airflow metadata (DAG runs, task instances, variables) |

### Prerequisites

- **PostgreSQL 16** (`postgres-airflow` service)
- **MinIO** (S3-compatible storage for Bronze Delta tables)
- **DuckDB 1.4.4** (querying Delta tables in DLQ monitoring)
- **delta-rs 1.4.2** (Delta Lake operations without Spark)
- **DBT 1.10.0** (with dbt-duckdb and dbt-spark)
- **Great Expectations** (data validation)
- **Trino** (SQL query engine for Silver/Gold layers)
- **Spark Thrift Server** (optional, for dual-engine DBT validation)

## Common Tasks

### Access Airflow Web UI

```bash
# Ensure data-pipeline services are running
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Open browser
open http://localhost:8082

# Login with credentials (default: admin/admin)
# Credentials set via AIRFLOW_ADMIN_USERNAME/AIRFLOW_ADMIN_PASSWORD env vars
```

### Manually Trigger a DAG

```bash
# Via Web UI: Navigate to DAG → Play button → Trigger DAG

# Via CLI (inside scheduler container)
docker exec rideshare-airflow-scheduler airflow dags trigger dbt_silver_transformation

# Trigger with config
docker exec rideshare-airflow-scheduler airflow dags trigger dbt_gold_transformation \
  --conf '{"triggered_by": "manual", "reason": "backfill"}'
```

### View Task Logs

```bash
# Via Web UI: DAG → Task Instance → Log tab

# Via CLI (inside scheduler container)
docker exec rideshare-airflow-scheduler airflow tasks logs dbt_silver_transformation dbt_silver_run 2026-02-13T10:10:00+00:00

# Via Docker logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-scheduler
```

### Check DLQ Error Counts

```bash
# View latest DLQ monitoring task logs in Web UI
# Or execute DLQ monitoring DAG manually:
docker exec rideshare-airflow-scheduler airflow dags trigger dlq_monitoring
```

### Pause/Unpause a DAG

```bash
# Via Web UI: Toggle switch next to DAG name

# Via CLI
docker exec rideshare-airflow-scheduler airflow dags pause dbt_silver_transformation
docker exec rideshare-airflow-scheduler airflow dags unpause dbt_silver_transformation
```

### Backfill Historical Data

```bash
# Backfill Silver transformations for specific date range
docker exec rideshare-airflow-scheduler airflow dags backfill \
  dbt_silver_transformation \
  --start-date 2026-02-01 \
  --end-date 2026-02-10
```

### Debug DAG Import Errors

```bash
# Check for DAG parsing errors
docker exec rideshare-airflow-scheduler airflow dags list-import-errors

# Test DAG file syntax
docker exec rideshare-airflow-scheduler python /opt/airflow/dags/dbt_transformation_dag.py
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| DAGs not appearing in Web UI | DAG parsing error or file not in `/opt/airflow/dags` | Check `airflow dags list-import-errors` and verify volume mount |
| `check_bronze_freshness` skips all tasks | Bronze tables don't exist yet | Expected on first deploy — DAG will proceed once bronze-ingestion populates tables |
| DLQ monitoring shows "Could not query table" | DLQ Delta tables not created yet | Expected on first run - tables created by stream-processor after errors occur |
| `dbt_silver_run` fails with "relation does not exist" | Bronze tables empty or missing | Ensure simulation and bronze-ingestion services are running |
| Webserver health check fails | Database migrations incomplete or port conflict | Check `airflow-webserver` logs and ensure PostgreSQL is healthy |
| Scheduler not picking up tasks | Scheduler not running or DAG paused | Verify `airflow-scheduler` container running and DAG toggled on in UI |
| "Permission denied" writing to `/opt/airflow/logs` | Volume mount ownership issue | Ensure `services/airflow/logs` directory exists and is writable |
| Delta maintenance fails with S3 auth error | MinIO credentials not loaded | Check `secrets-init` completed successfully and `data-pipeline.env` exists |

## Data Pipeline Flow

### Silver DAG (Hourly at :10)

```
check_bronze_freshness
  ↓
dbt_silver_run (tag:silver)
  ↓
dbt_silver_test
  ↓
ge_silver_validation (Great Expectations)
  ↓
export_silver_to_s3
  ↓
check_should_trigger_gold
  ↓
trigger_gold_dag (if 2 AM, manual run, or not PROD_MODE)
```

### Gold DAG (Triggered at 2 AM)

```
dbt_seed (reference data)
  ↓
dbt_gold_dimensions (tag:dimensions)
  ↓
dbt_gold_facts (tag:facts)
  ↓
dbt_gold_aggregates (tag:aggregates)
  ↓
dbt_gold_test (tag:gold)
  ↓
ge_gold_validation
  ↓
export_gold_to_s3
  ↓
ge_generate_data_docs
```

### DLQ Monitoring (Every 15 Minutes)

```
query_dlq_errors (DuckDB queries all DLQ tables)
  ↓
check_threshold (ERROR_THRESHOLD = 10)
  ↓
send_alert (if threshold exceeded) OR no_alert
```

### Delta Maintenance (3 AM Daily)

```
start
  ↓
check_data_exists (ShortCircuitOperator — skips if no Bronze tables)
  ↓
OPTIMIZE all Bronze + DLQ tables (parallel, max 4 at a time)
  ↓
optimize_complete
  ↓
VACUUM all Bronze + DLQ tables (parallel, 7-day retention)
  ↓
vacuum_complete
  ↓
summarize (metrics aggregation)
```

## Airflow Assets

DAGs use **Airflow Assets** for data lineage tracking:

- `SILVER_ASSET = Asset("lakehouse://silver/transformed")` - Produced by Silver DAG
- `GOLD_ASSET = Asset("lakehouse://gold/transformed")` - Produced by Gold DAG

Assets enable automatic dependency tracking and triggering in future enhancements.

## Production Mode

Set `PROD_MODE=true` to restrict Gold DAG execution to 2 AM only:

```bash
# In .env or docker-compose override
PROD_MODE=true

# With PROD_MODE=false (default):
# - Gold DAG triggers every hour after Silver completes
# - Useful for development/testing

# With PROD_MODE=true:
# - Gold DAG triggers only at 2 AM
# - Reduces compute load in production
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context, DAG patterns, orchestration strategy
- [dags/CONTEXT.md](dags/CONTEXT.md) - DAG implementation details and dependencies
- [../bronze-ingestion/README.md](../bronze-ingestion/README.md) - Upstream Kafka → Delta ingestion
- [../../tools/dbt/README.md](../../tools/dbt/README.md) - DBT transformation logic
- [../../tools/great-expectations/README.md](../../tools/great-expectations/README.md) - Data validation checkpoints
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Medallion architecture overview
