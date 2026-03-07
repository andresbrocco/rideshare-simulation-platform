# postgres-metastore

> PostgreSQL 16 backing store for Hive Metastore metadata — holds table definitions, schema registry, and partition information used by Trino for Delta Lake queries.

## Quick Reference

### Ports

| Host Port | Container Port | Purpose |
|-----------|---------------|---------|
| 5434 | 5432 | PostgreSQL wire protocol |

### Environment Variables

Credentials are never set as plain environment variables. They are injected at container startup from the secrets volume (`/secrets/data-pipeline.env`).

| Secret Key | Description |
|------------|-------------|
| `POSTGRES_METASTORE_USER` | PostgreSQL superuser name (default: `admin`) |
| `POSTGRES_METASTORE_PASSWORD` | PostgreSQL superuser password (default: `admin`) |

These keys live in the `rideshare/data-pipeline` secret group managed by LocalStack Secrets Manager. The `secrets-init` container fetches and writes them to `/secrets/data-pipeline.env` before this service starts.

To override defaults during local development:

```bash
OVERRIDE_POSTGRES_METASTORE_USER=myuser \
OVERRIDE_POSTGRES_METASTORE_PASSWORD=mypassword \
./venv/bin/python3 infrastructure/scripts/seed-secrets.py
```

### Database

| Setting | Value |
|---------|-------|
| Database name | `metastore` |
| Image | `postgres:16` |
| Data volume | `postgres-metastore-data` |
| Memory limit | 256 MB |

### Docker Compose

This service is part of the `data-pipeline` profile.

```bash
# Start with the full data-pipeline stack
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-metastore

# Start just postgres-metastore (also starts localstack + secrets-init)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-metastore
```

### Health Check

The container uses `pg_isready` to confirm the server accepts connections:

```bash
# Check health via Docker
docker inspect --format='{{.State.Health.Status}}' rideshare-postgres-metastore

# Manual check from host
pg_isready -h localhost -p 5434 -U admin
```

The service must be `healthy` before `hive-metastore` starts.

## Common Tasks

### Connect with psql

```bash
# From host (requires psql installed locally)
psql -h localhost -p 5434 -U admin -d metastore

# From inside the Docker network via another container
docker exec -it rideshare-postgres-metastore psql -U admin -d metastore
```

### Inspect Hive Metastore schema

After `hive-metastore` initializes, it auto-creates the Hive schema in this database. To inspect:

```bash
docker exec -it rideshare-postgres-metastore psql -U admin -d metastore -c "\dt"
```

Key tables include `TBLS`, `DBS`, `PARTITIONS`, `SDS`, and `COLUMNS_V2`.

### Reset database (wipe all metadata)

```bash
# Remove the named volume to start fresh
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline down
docker volume rm rideshare-simulation-platform_postgres-metastore-data
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d
```

### Tail logs

```bash
docker logs -f rideshare-postgres-metastore
```

## Troubleshooting

**hive-metastore fails to start with JDBC connection errors**

`postgres-metastore` was not yet healthy when `hive-metastore` launched, or the credentials in the secrets volume do not match. Verify:

```bash
docker inspect --format='{{.State.Health.Status}}' rideshare-postgres-metastore
# Should be "healthy"

docker exec rideshare-postgres-metastore sh -c '. /secrets/data-pipeline.env && echo $POSTGRES_METASTORE_USER'
# Should print the expected username
```

**Container exits immediately with "password authentication failed"**

The secrets volume may not have been populated before `postgres-metastore` started. Ensure `secrets-init` completed successfully:

```bash
docker logs rideshare-secrets-init
```

**`pg_isready` health check loops as "starting"**

PostgreSQL is still initializing its data directory. This is normal on first boot with an empty `postgres-metastore-data` volume. Allow up to 30 seconds (`start_period` in compose).

**Port 5434 already in use**

Another local PostgreSQL instance (or `postgres-airflow` on port 5432 if misconfigured) is occupying the port. Check with `lsof -i :5434` and stop the conflicting process.

## Related

- [services/hive-metastore/CONTEXT.md](../hive-metastore/CONTEXT.md) — Primary consumer of this database; manages Hive schema initialization
- [services/postgres-airflow/](../postgres-airflow/) — Sibling PostgreSQL instance for Airflow metadata (port 5432)
- [infrastructure/scripts/seed-secrets.py](../../infrastructure/scripts/seed-secrets.py) — Populates `POSTGRES_METASTORE_USER` and `POSTGRES_METASTORE_PASSWORD` in LocalStack
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) — Full service definition (lines 764-796)
