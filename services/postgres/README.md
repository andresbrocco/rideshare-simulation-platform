# PostgreSQL

> PostgreSQL 16 relational database service providing catalog and metadata persistence for the data pipeline layer

## Quick Reference

### Docker Services

| Service | Port (Host:Container) | Purpose | Profile |
|---------|----------------------|---------|---------|
| `postgres-airflow` | `5432:5432` | Airflow metadata database | `data-pipeline` |
| `postgres-metastore` | `5434:5432` | Hive metastore backend | `data-pipeline` |

### Environment Variables

Credentials are managed via **LocalStack Secrets Manager** and injected at runtime:

| Variable | Secret Path | Purpose |
|----------|-------------|---------|
| `POSTGRES_AIRFLOW_USER` | `rideshare/postgres-airflow` | Airflow database username |
| `POSTGRES_AIRFLOW_PASSWORD` | `rideshare/postgres-airflow` | Airflow database password |
| `POSTGRES_METASTORE_USER` | `rideshare/postgres-metastore` | Metastore database username |
| `POSTGRES_METASTORE_PASSWORD` | `rideshare/postgres-metastore` | Metastore database password |

**Default Development Values**: All credentials default to `admin` for username/password.

### Connection Strings

**Airflow** (SQLAlchemy):
```bash
postgresql+psycopg2://${POSTGRES_AIRFLOW_USER}:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/airflow
```

**Hive Metastore** (JDBC):
```bash
jdbc:postgresql://postgres-metastore:5432/metastore
```

### Data Volumes

| Volume | Service | Data |
|--------|---------|------|
| `postgres-airflow-data` | postgres-airflow | DAG runs, task instances, XCom, connections |
| `postgres-metastore-data` | postgres-metastore | Table definitions, partitions, schemas |

## Common Tasks

### Start PostgreSQL Services

Both instances are part of the `data-pipeline` profile:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow postgres-metastore
```

### Check Service Health

```bash
# Check both instances
docker compose -f infrastructure/docker/compose.yml ps postgres-airflow postgres-metastore

# View logs
docker compose -f infrastructure/docker/compose.yml logs postgres-airflow
docker compose -f infrastructure/docker/compose.yml logs postgres-metastore
```

### Connect to Database

**Airflow Instance** (from host):
```bash
psql -h localhost -p 5432 -U admin -d airflow
# Password: admin
```

**Metastore Instance** (from host):
```bash
psql -h localhost -p 5434 -U admin -d metastore
# Password: admin
```

**From another container** (using service name):
```bash
# Airflow
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver \
  psql postgresql://admin:admin@postgres-airflow:5432/airflow  # pragma: allowlist secret

# Metastore
docker compose -f infrastructure/docker/compose.yml exec hive-metastore \
  psql postgresql://admin:admin@postgres-metastore:5432/metastore  # pragma: allowlist secret
```

### Inspect Airflow Metadata

```bash
# List DAG runs
psql -h localhost -p 5432 -U admin -d airflow -c "SELECT dag_id, state, execution_date FROM dag_run ORDER BY execution_date DESC LIMIT 10;"

# Check task instance status
psql -h localhost -p 5432 -U admin -d airflow -c "SELECT dag_id, task_id, state, start_date FROM task_instance WHERE dag_id='your_dag_id' ORDER BY start_date DESC LIMIT 10;"
```

### Inspect Hive Metastore Catalog

```bash
# List tables
psql -h localhost -p 5434 -U admin -d metastore -c "SELECT t.tbl_name, d.name as db_name FROM \"TBLS\" t JOIN \"DBS\" d ON t.db_id = d.db_id;"

# Check partitions for a table
psql -h localhost -p 5434 -U admin -d metastore -c "SELECT p.part_name FROM \"PARTITIONS\" p JOIN \"TBLS\" t ON p.tbl_id = t.tbl_id WHERE t.tbl_name = 'your_table_name';"
```

### Reset Database (Development Only)

```bash
# Stop services and remove volumes
docker compose -f infrastructure/docker/compose.yml down -v

# Restart - databases will be reinitialized
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow postgres-metastore
```

## Prerequisites

- Docker with Compose V2
- `secrets-init` service must complete successfully (provides credentials)
- 256MB available memory per instance

## Troubleshooting

### Service Won't Start

**Check secrets initialization**:
```bash
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

**Verify health check**:
```bash
docker compose -f infrastructure/docker/compose.yml exec postgres-airflow pg_isready -U admin
docker compose -f infrastructure/docker/compose.yml exec postgres-metastore pg_isready -U admin
```

### Connection Refused

**Check service is running**:
```bash
docker compose -f infrastructure/docker/compose.yml ps postgres-airflow postgres-metastore
```

**Verify port mapping**:
```bash
docker compose -f infrastructure/docker/compose.yml port postgres-airflow 5432
docker compose -f infrastructure/docker/compose.yml port postgres-metastore 5432
```

### Airflow Can't Connect to Database

**Check connection string** in airflow-webserver/airflow-scheduler environment:
```bash
docker compose -f infrastructure/docker/compose.yml exec airflow-webserver env | grep SQL_ALCHEMY_CONN
```

**Verify credentials** match between postgres-airflow and Airflow services:
```bash
docker compose -f infrastructure/docker/compose.yml exec postgres-airflow sh -c '. /secrets/data-pipeline.env && echo $POSTGRES_AIRFLOW_USER'
```

### Hive Metastore Can't Connect to Database

**Check JDBC connection** in hive-metastore logs:
```bash
docker compose -f infrastructure/docker/compose.yml logs hive-metastore | grep -i "connection"
```

**Verify metastore database exists**:
```bash
psql -h localhost -p 5434 -U admin -c "\l"
```

### Data Loss After Restart

**Verify named volumes exist**:
```bash
docker volume ls | grep postgres
```

**Check volume mounts**:
```bash
docker compose -f infrastructure/docker/compose.yml config | grep -A 5 "postgres-airflow-data"
```

### Performance Issues

Both instances have 256MB memory limits. Check memory usage:
```bash
docker stats postgres-airflow postgres-metastore
```

If queries are slow, inspect database statistics:
```bash
psql -h localhost -p 5432 -U admin -d airflow -c "SELECT * FROM pg_stat_activity;"
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and responsibility boundaries
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) — Service definitions
- [../airflow/CONTEXT.md](../airflow/CONTEXT.md) — Airflow workflow orchestration
- [../hive-metastore/CONTEXT.md](../hive-metastore/CONTEXT.md) — Hive Metastore catalog service
