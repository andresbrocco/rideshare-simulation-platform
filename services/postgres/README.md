# PostgreSQL Configuration

PostgreSQL 16 metadata databases for Airflow and Hive Metastore.

## Purpose

This directory documents two independent PostgreSQL 16 instances that provide relational storage for the data pipeline layer. Both use the stock `postgres:16` image with no custom configuration files -- all settings are defined via environment variables in `infrastructure/docker/compose.yml`.

## Instances

| Instance | Host Port | User | Database | Volume | Purpose |
|----------|-----------|------|----------|--------|---------|
| `postgres-airflow` | `5432` | `airflow` | `airflow` | `postgres-airflow-data` | Airflow workflow metadata |
| `postgres-metastore` | `5434` | `hive` | `metastore` | `postgres-metastore-data` | Hive Metastore catalog |

## Configuration

| Setting | Value |
|---------|-------|
| **Image** | `postgres:16` |
| **Memory Limit** | 256MB (each instance) |
| **Profile** | `data-pipeline` |
| **Custom Config Files** | None (stock image, env vars only) |

## Usage

### Start Both Instances

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow postgres-metastore
```

### Health Check

```bash
# postgres-airflow
docker exec rideshare-postgres-airflow pg_isready -U airflow

# postgres-metastore
docker exec rideshare-postgres-metastore pg_isready -U hive
```

### Connect via psql

```bash
# Airflow database
psql -h localhost -p 5432 -U airflow -d airflow

# Metastore database
psql -h localhost -p 5434 -U hive -d metastore
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs postgres-airflow
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs postgres-metastore
```

### List Tables in Each Database

```bash
# Airflow tables
psql -h localhost -p 5432 -U airflow -d airflow -c "\dt"

# Metastore tables
psql -h localhost -p 5434 -U hive -d metastore -c "\dt"
```

## Troubleshooting

### postgres-airflow not healthy

Check the container status and logs:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline ps postgres-airflow
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs postgres-airflow
```

### postgres-metastore not healthy

Check the container status and logs:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline ps postgres-metastore
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs postgres-metastore
```

### Port 5432 already in use

A local PostgreSQL installation may conflict with `postgres-airflow`. Stop the local instance or change the host port in `infrastructure/docker/compose.yml`.

### Stale data after schema changes

If a service upgrade requires a schema migration that fails, remove the volume and let the service recreate it:

```bash
# Airflow
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline down
docker volume rm rideshare-simulation-platform_postgres-airflow-data
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-airflow

# Metastore
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline down
docker volume rm rideshare-simulation-platform_postgres-metastore-data
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-metastore
```

## References

- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
