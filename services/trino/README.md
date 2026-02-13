# Trino

> Distributed SQL query engine for interactive analytical queries over Delta Lake tables in the medallion lakehouse

## Quick Reference

### Service

| Property | Value |
|----------|-------|
| Image | `trinodb/trino:439` |
| Port | `8084` (host) → `8080` (container) |
| Profile | `data-pipeline` |
| Health Check | `http://localhost:8084/v1/info` |

### Prerequisites

- **hive-metastore**: Table metadata and schema resolution (Thrift port 9083)
- **minio**: S3-compatible object storage for Delta Lake data
- **secrets-init**: Credentials from LocalStack Secrets Manager (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`)

### Configuration

| File | Purpose |
|------|---------|
| `etc/config.properties` | Coordinator settings, HTTP server port 8080, discovery URI |
| `etc/jvm.config` | JVM tuning: 1GB heap, G1GC, 32MB region size, 256MB code cache |
| `etc/node.properties` | Node identifier (auto-generated) |
| `etc/catalog/delta.properties.template` | Delta Lake connector template (envsubst) |
| `etc/catalog/delta.properties` | Generated Delta Lake connector config |
| `entrypoint.sh` | Loads secrets and substitutes env vars before starting Trino |

## Common Tasks

### Query Delta Lake Tables

```bash
# Connect to Trino CLI (via Docker exec)
docker exec -it trino trino

# List catalogs
SHOW CATALOGS;

# Show schemas in delta catalog
SHOW SCHEMAS FROM delta;

# Query bronze layer
SELECT * FROM delta.bronze.trips LIMIT 10;

# Query silver layer (DBT-transformed)
SELECT * FROM delta.silver.cleaned_trips LIMIT 10;

# Query gold layer (analytics)
SELECT * FROM delta.gold.trip_metrics_daily LIMIT 10;
```

### Test Trino Connection

```bash
# Health check
curl http://localhost:8084/v1/info

# Grafana integration (trino-datasource plugin uses HTTP API)
curl -u admin:admin http://localhost:8084/v1/statement \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT 1 AS test"}'
```

### Start Trino Service

```bash
# Start data-pipeline profile (includes trino, hive-metastore, minio)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# Check Trino logs
docker compose -f infrastructure/docker/compose.yml logs -f trino

# Verify Trino is healthy
docker compose -f infrastructure/docker/compose.yml ps trino
```

### Debug Catalog Issues

```bash
# Check delta.properties generation
docker exec -it trino cat /etc/trino/catalog/delta.properties

# Verify Hive Metastore connectivity
docker exec -it trino curl -v http://hive-metastore:9083

# Check MinIO S3 access
docker exec -it trino curl -v http://minio:9000/minio/health/live
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Connection refused` to metastore | Hive Metastore not running or unhealthy | Check `docker compose ps hive-metastore` and logs |
| Queries fail with S3 errors | MinIO credentials incorrect or service down | Verify `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` in `/secrets/data-pipeline.env` |
| Port 8084 already in use | Another service using host port | Stop conflicting service or change host port mapping |
| Trino starts but catalog queries fail | Metastore or MinIO not accessible | Ensure `hive-metastore` and `minio` are healthy before starting Trino |
| `delta.properties` missing | `entrypoint.sh` failed to generate config | Check Trino logs for envsubst/sed errors; verify secrets volume mounted |
| Grafana dashboard queries fail | Numeric format required for `trino-datasource` | Ensure `"format": 0` (table) or `"format": 1` (time_series) in JSON |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture and non-obvious details
- [../hive-metastore/README.md](../hive-metastore/README.md) — Metadata service
- [../minio/README.md](../minio/README.md) — Object storage
- [../../tools/dbt/README.md](../../tools/dbt/README.md) — DBT transformations
- [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Medallion lakehouse design
