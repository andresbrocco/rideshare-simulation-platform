# Airflow Service

> Apache Airflow 3.1.5 orchestration control plane for medallion pipeline scheduling and DLQ monitoring

## Quick Reference

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `AIRFLOW__CORE__EXECUTOR` | `LocalExecutor` | Task execution within scheduler process |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | `postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow` | Metadata database connection |
| `AIRFLOW__CORE__LOAD_EXAMPLES` | `false` | Disable example DAGs |
| `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION` | `true` | New DAGs start paused |
| `AIRFLOW__CORE__PARALLELISM` | `8` | Max concurrent tasks |
| `AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL` | `30` | DAG scan interval (seconds) |
| `AIRFLOW__CORE__AUTH_MANAGER` | `airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager` | Authentication manager |
| `AIRFLOW_HOME` | `/opt/airflow` | Airflow home directory |
| `DBT_SPARK_HOST` | `spark-thrift-server` | DBT Spark connection host |

### Ports

| Port | Service | Purpose |
|------|---------|---------|
| 8082 | Webserver UI | http://localhost:8082 |
| 5432 | PostgreSQL | Internal metadata database |

### DAGs

| DAG ID | Schedule | Purpose |
|--------|----------|---------|
| `dbt_silver_transformation` | `@hourly` | Silver layer transformations with Great Expectations validation |
| `dbt_gold_transformation` | `@daily` | Gold layer transformations (dimensions → facts → aggregates) |
| `dlq_monitoring` | Every 15 min | Monitor DLQ tables for errors (threshold: 10) |
| `bronze_initialization` | Manual | Initialize Bronze database in Hive metastore (one-time) |
| `streaming_jobs_lifecycle` | None | DEPRECATED - managed via docker compose services |

### Commands

```bash
# Start Airflow services (from project root)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-webserver
docker compose -f infrastructure/docker/compose.yml logs -f airflow-scheduler

# Access UI (login with admin/admin)
open http://localhost:8082

# Manually trigger a DAG
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags trigger dbt_silver_transformation

# List all DAGs
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags list

# Pause/unpause a DAG
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags pause dbt_gold_transformation
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags unpause dbt_gold_transformation

# Reserialize DAGs (Airflow 3.x)
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags reserialize
```

### Prerequisites

- PostgreSQL 16 (postgres-airflow service)
- Spark Thrift Server (for DBT tasks)
- MinIO (for Great Expectations data docs)
- DBT project at `services/dbt/`
- Great Expectations suite at `quality/great-expectations/`

### Configuration

Key configuration files:

- `config/connections.yaml` - Airflow connections (Spark, Databricks)
- `dags/` - DAG definitions
- `logs/` - Task execution logs
- `plugins/` - Custom plugins

Installed providers (via `_PIP_ADDITIONAL_REQUIREMENTS`):
- `apache-airflow-providers-fab` - Flask AppBuilder authentication
- `apache-airflow-providers-apache-spark` - Spark integration
- `pyhive` - Hive Thrift Server client
- `thrift` - Thrift protocol support
- `dbt-core` - DBT core library
- `dbt-spark[PyHive]` - DBT Spark adapter with PyHive

## Common Tasks

### Add a New DAG

1. Create DAG file in `services/airflow/dags/`
2. DAG will be scanned within 30 seconds
3. Appears in UI automatically (paused by default)
4. Unpause to activate

Example DAG structure:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

default_args = {
    "owner": "rideshare",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "my_dag",
    default_args=default_args,
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["my-tag"],
) as dag:
    task = BashOperator(
        task_id="my_task",
        bash_command="echo 'Hello World'",
    )
```

### Monitor DLQ Errors

DLQ monitoring runs every 15 minutes and checks 8 DLQ tables:

- `dlq_trips`
- `dlq_gps_pings`
- `dlq_driver_status`
- `dlq_surge_updates`
- `dlq_ratings`
- `dlq_payments`
- `dlq_driver_profiles`
- `dlq_rider_profiles`

Alert threshold: 10 errors in 15-minute window.

Query DLQ manually:

```bash
# Connect to Spark Thrift Server via PyHive
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler python3 -c "
from pyhive import hive
conn = hive.connect(host='spark-thrift-server', port=10000, auth='NOSASL')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM bronze.dlq_gps_pings')
print(cursor.fetchone())
"
```

### Run DBT Transformations Manually

```bash
# Run Silver layer
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler \
  airflow dags trigger dbt_silver_transformation

# Run Gold layer
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler \
  airflow dags trigger dbt_gold_transformation

# Or run DBT directly
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler bash -c \
  "cd /opt/dbt && dbt run --select tag:silver --profiles-dir /opt/dbt/profiles"
```

### Initialize Bronze Layer (First Deployment)

```bash
# Trigger one-time Bronze initialization
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler \
  airflow dags trigger bronze_initialization

# Check logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-scheduler
```

## Architecture

- **Executor**: LocalExecutor (task subprocesses within scheduler)
- **Metadata Database**: PostgreSQL 16
- **Webserver Memory**: 384MB
- **Scheduler Memory**: 384MB
- **Database Memory**: 256MB
- **Total Memory**: 1024MB (1GB)

**Scheduler Health Check**: Socket connection to port 8793
**Webserver Health Check**: HTTP GET `/api/v2/monitor/health`

## Health Checks

- **Webserver**: `http://localhost:8082/api/v2/monitor/health`
- **Scheduler**: Socket check on port 8793
- **Database**: `pg_isready -U airflow`

Check service health:

```bash
docker compose -f infrastructure/docker/compose.yml ps airflow-webserver
docker compose -f infrastructure/docker/compose.yml ps airflow-scheduler
docker compose -f infrastructure/docker/compose.yml ps postgres-airflow
```

## Default Credentials

Airflow 3.x uses Flask AppBuilder Auth Manager with static admin credentials.

- **Username**: `admin`
- **Password**: `admin`

Access UI at http://localhost:8082

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture context
- [services/dbt/](../dbt/) - DBT transformations
- [quality/great-expectations/](../../quality/great-expectations/) - Data validation
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker services

---

## Additional Notes

### Troubleshooting

#### Webserver won't start
- Check PostgreSQL is healthy: `docker compose -f infrastructure/docker/compose.yml ps postgres-airflow`
- View logs: `docker compose -f infrastructure/docker/compose.yml logs postgres-airflow`

#### DAGs not appearing
- Verify DAG syntax: `docker compose -f infrastructure/docker/compose.yml exec airflow-webserver airflow dags list`
- Check scheduler logs: `docker compose -f infrastructure/docker/compose.yml logs airflow-scheduler`
- Manually reserialize: `docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler airflow dags reserialize`

#### Memory issues
- LocalExecutor spawns task subprocesses within scheduler
- Reduce parallelism if scheduler OOM restarts occur
- Current limit: 8 concurrent tasks
- Adjust `AIRFLOW__CORE__PARALLELISM` environment variable if needed
