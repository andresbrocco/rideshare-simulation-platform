# PostgreSQL (Airflow)

> PostgreSQL 16 instance storing Airflow workflow metadata

## Quick Reference

| Property | Value |
|----------|-------|
| Service | `postgres-airflow` |
| Port (Host:Container) | `5432:5432` |
| Profile | `data-pipeline` |
| Image | `postgres:16` |
| Memory Limit | 256MB |

### Environment Variables

Credentials are managed via **LocalStack Secrets Manager** and injected at runtime:

| Variable | Secret Path | Purpose |
|----------|-------------|---------|
| `POSTGRES_AIRFLOW_USER` | `rideshare/data-pipeline` | Database username |
| `POSTGRES_AIRFLOW_PASSWORD` | `rideshare/data-pipeline` | Database password |

**Default Development Values**: `admin` / `admin`

### Connection String

**SQLAlchemy** (used by Airflow):
```bash
postgresql+psycopg2://${POSTGRES_AIRFLOW_USER}:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/airflow
```

### Data Volume

| Volume | Data |
|--------|------|
| `postgres-airflow-data` | DAG runs, task instances, XCom, connections |

## Common Tasks

### Start Service

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow
```

### Check Health

```bash
docker compose -f infrastructure/docker/compose.yml ps postgres-airflow
docker compose -f infrastructure/docker/compose.yml logs postgres-airflow
```

### Connect to Database

**From host**:
```bash
psql -h localhost -p 5432 -U admin -d airflow
# Password: admin
```

**From another container**:
```bash
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver \
  psql postgresql://admin:admin@postgres-airflow:5432/airflow
```

### Inspect Airflow Metadata

```bash
# List DAG runs
psql -h localhost -p 5432 -U admin -d airflow -c "SELECT dag_id, state, execution_date FROM dag_run ORDER BY execution_date DESC LIMIT 10;"

# Check task instance status
psql -h localhost -p 5432 -U admin -d airflow -c "SELECT dag_id, task_id, state, start_date FROM task_instance ORDER BY start_date DESC LIMIT 10;"
```

### Reset Database (Development Only)

```bash
docker compose -f infrastructure/docker/compose.yml down -v
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow
```

## Prerequisites

- Docker with Compose V2
- `secrets-init` service must complete successfully (provides credentials)

## Troubleshooting

### Service Won't Start

```bash
# Check secrets initialization
docker compose -f infrastructure/docker/compose.yml logs secrets-init

# Verify health check
docker compose -f infrastructure/docker/compose.yml exec postgres-airflow pg_isready -U admin
```

### Airflow Can't Connect

```bash
# Check connection string in Airflow
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver env | grep SQL_ALCHEMY_CONN

# Verify credentials match
docker compose -f infrastructure/docker/compose.yml exec postgres-airflow sh -c '. /secrets/data-pipeline.env && echo $POSTGRES_AIRFLOW_USER'
```

## Related

- [CONTEXT.md](CONTEXT.md) -- Architecture and responsibility boundaries
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) -- Service definition
- [../airflow/CONTEXT.md](../airflow/CONTEXT.md) -- Airflow workflow orchestration
