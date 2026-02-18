# PostgreSQL (Metastore)

> PostgreSQL 16 instance storing the Hive Metastore catalog for Delta Lake table discovery

## Quick Reference

| Property | Value |
|----------|-------|
| Service | `postgres-metastore` |
| Port (Host:Container) | `5434:5432` |
| Profile | `data-pipeline` |
| Image | `postgres:16` |
| Memory Limit | 256MB |

### Environment Variables

Credentials are managed via **LocalStack Secrets Manager** and injected at runtime:

| Variable | Secret Path | Purpose |
|----------|-------------|---------|
| `POSTGRES_METASTORE_USER` | `rideshare/data-pipeline` | Database username |
| `POSTGRES_METASTORE_PASSWORD` | `rideshare/data-pipeline` | Database password |

**Default Development Values**: `admin` / `admin`

### Connection String

**JDBC** (used by Hive Metastore):
```bash
jdbc:postgresql://postgres-metastore:5432/metastore
```

### Data Volume

| Volume | Data |
|--------|------|
| `postgres-metastore-data` | Table definitions, partitions, schemas, SerDe info |

## Common Tasks

### Start Service

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-metastore
```

### Check Health

```bash
docker compose -f infrastructure/docker/compose.yml ps postgres-metastore
docker compose -f infrastructure/docker/compose.yml logs postgres-metastore
```

### Connect to Database

**From host**:
```bash
psql -h localhost -p 5434 -U admin -d metastore
# Password: admin
```

**From another container**:
```bash
docker compose -f infrastructure/docker/compose.yml exec hive-metastore \
  psql postgresql://admin:admin@postgres-metastore:5432/metastore
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
docker compose -f infrastructure/docker/compose.yml down -v
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d postgres-metastore
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
docker compose -f infrastructure/docker/compose.yml exec postgres-metastore pg_isready -U admin
```

### Hive Metastore Can't Connect

```bash
# Check JDBC connection in hive-metastore logs
docker compose -f infrastructure/docker/compose.yml logs hive-metastore | grep -i "connection"

# Verify metastore database exists
psql -h localhost -p 5434 -U admin -c "\l"
```

## Related

- [CONTEXT.md](CONTEXT.md) -- Architecture and responsibility boundaries
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) -- Service definition
- [../hive-metastore/CONTEXT.md](../hive-metastore/CONTEXT.md) -- Hive Metastore catalog service
