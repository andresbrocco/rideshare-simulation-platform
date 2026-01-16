# Airflow Service

Apache Airflow 3.1.5 for orchestrating data quality checks and DBT pipeline runs.

## Architecture

- **Executor**: LocalExecutor (task execution within scheduler process)
- **Metadata Database**: PostgreSQL 16
- **Webserver**: 384MB memory limit
- **Scheduler**: 384MB memory limit
- **Database**: 256MB memory limit
- **Total Memory**: 1024MB (1GB)

## Quick Start

```bash
# Start Airflow services (from project root)
docker compose -f infrastructure/docker/compose.yml --profile quality-orchestration up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f airflow-webserver
docker compose -f infrastructure/docker/compose.yml logs -f airflow-scheduler

# Access UI
open http://localhost:8082
```

## Default Credentials

Airflow 3.x uses Simple Auth Manager by default, which generates a random admin password on first startup.

- **Username**: `admin`
- **Password**: Check logs for generated password

To get the password:
```bash
docker compose -f infrastructure/docker/compose.yml logs airflow-webserver | grep "Password for user"
```

Example output:
```
Simple auth manager | Password for user 'admin': 2DdvTTV3azq96QTs
```

## Configuration

Key settings configured via environment variables:

- `AIRFLOW__CORE__EXECUTOR=LocalExecutor` - Local task execution
- `AIRFLOW__CORE__PARALLELISM=8` - Max 8 concurrent tasks
- `AIRFLOW__CORE__LOAD_EXAMPLES=false` - No example DAGs
- `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true` - New DAGs start paused

## Directory Structure

```
services/airflow/
├── dags/          # DAG definitions
├── logs/          # Task execution logs
├── plugins/       # Custom plugins
├── config/        # Configuration files
└── requirements.txt
```

## DAG Development

1. Add DAG files to `dags/` directory
2. DAGs are scanned every 30 seconds
3. New DAGs appear in UI automatically
4. Logs written to `logs/` directory

## Health Checks

- **Webserver**: `http://localhost:8082/health`
- **Scheduler**: Uses `airflow jobs check` command
- **Database**: PostgreSQL `pg_isready` check

## Troubleshooting

### Webserver won't start
- Check PostgreSQL is healthy: `docker compose ps postgres-airflow`
- View logs: `docker compose logs postgres-airflow`

### DAGs not appearing
- Verify DAG syntax: `docker compose exec airflow-webserver airflow dags list`
- Check scheduler logs: `docker compose logs airflow-scheduler`

### Memory issues
- LocalExecutor spawns task subprocesses within scheduler
- Reduce parallelism if scheduler OOM restarts occur
- Current limit: 8 concurrent tasks

## Ports

- **8082**: Airflow webserver UI
- **5432**: PostgreSQL (internal)
