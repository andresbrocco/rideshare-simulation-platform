# Airflow

> Orchestrates the medallion lakehouse pipeline: hourly Silver DBT transforms, daily Gold DBT transforms, daily Delta Lake maintenance, and 15-minute DLQ error monitoring.

## Quick Reference

### Ports

| Port (host) | Port (container) | Service              | Description        |
|-------------|------------------|----------------------|--------------------|
| 8082        | 8080             | airflow-webserver    | Airflow web UI     |

### Environment Variables

| Variable                   | Default              | Description                                                                 |
|----------------------------|----------------------|-----------------------------------------------------------------------------|
| `DBT_RUNNER`               | `duckdb`             | Controls DAG topology. `duckdb` adds S3 export + Trino registration steps; `glue` uses Glue Interactive Sessions and skips those steps. **Requires scheduler restart if changed.** |
| `SILVER_SCHEDULE`          | `10 * * * *`         | Cron expression for the Silver DAG. Offset by 10 minutes to allow Bronze ingestion to settle. |
| `PROD_MODE`                | `false`              | When `true`, the Silver DAG only triggers the Gold DAG on the 2 AM scheduled run. Non-prod and manual runs always trigger Gold. |
| `AIRFLOW_ADMIN_USERNAME`   | (from secrets)       | Web UI admin username. Loaded from LocalStack Secrets Manager at runtime.   |
| `AIRFLOW_ADMIN_PASSWORD`   | (from secrets)       | Web UI admin password. Loaded from LocalStack Secrets Manager at runtime.   |
| `POSTGRES_AIRFLOW_USER`    | (from secrets)       | PostgreSQL metadata DB username.                                            |
| `POSTGRES_AIRFLOW_PASSWORD`| (from secrets)       | PostgreSQL metadata DB password.                                            |
| `AWS_ENDPOINT_URL`         | _(unset in prod)_    | MinIO endpoint for local dev (`http://minio:9000`). Absent in production — triggers IAM Pod Identity credential chain. |
| `BRONZE_BUCKET`            | `rideshare-bronze`   | S3/MinIO bucket name that holds Bronze and DLQ Delta tables.                |
| `AWS_REGION`               | `us-east-1`          | AWS region used in production.                                              |

### DAGs

| DAG ID                    | Schedule            | Trigger Source       | Description                                                                 |
|---------------------------|---------------------|----------------------|-----------------------------------------------------------------------------|
| `dbt_silver_transformation` | `10 * * * *` (configurable via `SILVER_SCHEDULE`) | Time | Bronze freshness check → DBT Silver run/test → GE validation → (optional S3 export + Trino registration) → Gold trigger decision |
| `dbt_gold_transformation` | `None` (no schedule) | Silver DAG at 2 AM or manual | DBT seed → dimensions → facts → aggregates → test → GE validation → (optional S3 export + Trino registration) → data docs |
| `delta_maintenance`       | `0 3 * * *`         | Time (daily 3 AM)    | Bronze freshness check → OPTIMIZE all Bronze + DLQ tables → VACUUM all tables |
| `dlq_monitoring`          | `3,18,33,48 * * * *` | Time (every ~15 min) | Query all DLQ Delta tables via DuckDB; alert if >10 errors in the last 15 minutes |

### Docker Services

| Service               | Image                     | Profile        |
|-----------------------|---------------------------|----------------|
| `airflow-webserver`   | `apache/airflow:3.1.5`    | `data-pipeline`|
| `airflow-scheduler`   | `apache/airflow:3.1.5`    | `data-pipeline`|
| `postgres-airflow`    | `postgres:16`             | `data-pipeline`|

### Installed Packages (via `_PIP_ADDITIONAL_REQUIREMENTS`)

```
apache-airflow-providers-amazon
apache-airflow-providers-fab
dbt-core
dbt-duckdb==1.10.0
dbt-glue==1.10.15
duckdb==1.4.4
deltalake==1.4.2
duckdb-engine==0.17.0
great-expectations
requests
prison
```

### Bronze Tables Monitored

```
bronze_trips            bronze_gps_pings         bronze_driver_status
bronze_surge_updates    bronze_ratings           bronze_payments
bronze_driver_profiles  bronze_rider_profiles
```

DLQ tables follow the naming convention `dlq_<bronze_table_name>` (e.g., `dlq_bronze_trips`).

## Common Tasks

### Start Airflow (local dev)

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d
```

### Open the web UI

```
http://localhost:8082
```

Default credentials are managed via LocalStack Secrets Manager. The seeded admin username is `admin`.

### Unpause all DAGs via the Airflow CLI

```bash
docker exec rideshare-airflow-webserver airflow dags unpause dbt_silver_transformation
docker exec rideshare-airflow-webserver airflow dags unpause dbt_gold_transformation
docker exec rideshare-airflow-webserver airflow dags unpause delta_maintenance
docker exec rideshare-airflow-webserver airflow dags unpause dlq_monitoring
```

### Trigger the Silver DAG manually (skipping schedule)

```bash
docker exec rideshare-airflow-webserver airflow dags trigger dbt_silver_transformation
```

### Trigger the Gold DAG manually

```bash
docker exec rideshare-airflow-webserver airflow dags trigger dbt_gold_transformation
```

### Switch to Glue runner

Set `DBT_RUNNER=glue` in your environment before starting the stack, then restart the scheduler so Airflow re-parses the DAG topology:

```bash
DBT_RUNNER=glue docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d
```

### Run a manual DLQ check

```bash
docker exec rideshare-airflow-webserver airflow dags trigger dlq_monitoring
```

### Force Delta maintenance (OPTIMIZE + VACUUM)

```bash
docker exec rideshare-airflow-webserver airflow dags trigger delta_maintenance
```

## Troubleshooting

### Silver DAG skips all tasks silently

The `check_bronze_freshness` ShortCircuitOperator returns `False` when Bronze Delta tables do not exist yet. This is normal before the simulation has produced any data. Start the simulation and wait for bronze-ingestion to write at least one file to each Bronze table before the Silver DAG will proceed.

### DAG topology looks wrong after changing `DBT_RUNNER`

The DAG topology (number and identity of tasks) is determined at module import time. Airflow caches the parsed structure. After changing `DBT_RUNNER`, restart the scheduler container:

```bash
docker compose -f infrastructure/docker/compose.yml restart airflow-scheduler
```

### Gold DAG never runs automatically in production

`PROD_MODE=true` restricts the Silver → Gold trigger to the 2 AM scheduled run only. All other hourly Silver runs skip the Gold trigger. Trigger manually if you need Gold data outside of 2 AM.

### GE validation failure does not fail the DAG

Great Expectations checkpoints use `|| echo "WARNING" && exit 0`, so validation failures are soft — they log a warning but do not block subsequent tasks. Check Airflow logs for `WARNING: Silver/Gold validation failed` to detect silent GE failures.

### DLQ alert fires but no external notification is received

The `send_alert` task logs the threshold breach to Airflow task logs only. No external notification system (email, Slack, PagerDuty) is currently wired. Check the `dlq_monitoring` DAG logs in the web UI at `http://localhost:8082`.

### `stg_ratings` / `stg_payments` have 0 rows

These tables are populated only after trips complete. 0 rows early in a simulation run is expected. The Trino registration script skips tables where Delta transaction log is absent — no action required.

### Cannot connect to MinIO from within the DAG

Verify `AWS_ENDPOINT_URL=http://minio:9000` is set on the scheduler container, and that MinIO is healthy:

```bash
docker inspect rideshare-minio | grep '"Status"'
curl http://localhost:9001/minio/health/live
```

## Configuration Files

| Path                             | Description                                      |
|----------------------------------|--------------------------------------------------|
| `services/airflow/dags/`         | DAG source files (mounted into containers)       |
| `services/airflow/config/connections.yaml` | Airflow connection definitions (loaded at startup) |
| `services/airflow/plugins/`      | Custom Airflow plugins (currently empty)         |
| `services/airflow/logs/`         | Task execution logs (mounted volume)             |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, DAG topology decisions, and non-obvious behaviors
- [services/airflow/dags/CONTEXT.md](dags/CONTEXT.md) — DAG-level concepts: Asset lineage, DLQ querying via DuckDB
- [tools/dbt/README.md](../../tools/dbt/README.md) — DBT project for Silver and Gold transformations
- [tools/great-expectations/README.md](../../tools/great-expectations/README.md) — GE checkpoints used in Silver and Gold validation steps
- [services/bronze-ingestion/README.md](../bronze-ingestion/README.md) — Writes the Bronze Delta tables that Airflow gates on
- [infrastructure/scripts/README.md](../../infrastructure/scripts/README.md) — `register-trino-tables.py`, `export-dbt-to-s3.py`, `register-glue-tables.py` called by DAG tasks
