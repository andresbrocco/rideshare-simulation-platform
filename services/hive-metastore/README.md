# Hive Metastore

> Table metadata catalog for Delta Lake tables, enabling Trino to query Silver and Gold lakehouse data via the `delta` connector.

## Quick Reference

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 9083 | Thrift | Hive Metastore Thrift server (client URI: `thrift://hive-metastore:9083`) |

### Environment Variables

Credentials are never passed as Docker environment variables directly. They are injected from `/secrets/data-pipeline.env` by the `secrets-init` sidecar at startup. The following variables must be present in that secrets file:

| Variable | Description |
|----------|-------------|
| `POSTGRES_METASTORE_USER` | PostgreSQL username for the metastore backend |
| `POSTGRES_METASTORE_PASSWORD` | PostgreSQL password for the metastore backend |
| `MINIO_ROOT_USER` | MinIO/S3 access key for S3A filesystem access |
| `MINIO_ROOT_PASSWORD` | MinIO/S3 secret key for S3A filesystem access |

The following are set directly as Docker environment variables (non-secret):

| Variable | Value | Description |
|----------|-------|-------------|
| `SERVICE_NAME` | `metastore` | Hive service mode selector |
| `DB_DRIVER` | `postgres` | JDBC driver type |
| `SERVICE_OPTS` | JVM flags | Heap limit (`-Xmx768m`) and JDBC connection properties |
| `DB_HOST` | `postgres-metastore` (default) | PostgreSQL host for readiness check |
| `DB_PORT` | `5432` (default) | PostgreSQL port for readiness check |

### Configuration Files

| File | Purpose |
|------|---------|
| `hive-site.xml.template` | Canonical config with `${VAR}` placeholders — source of truth, mounted read-only into the container |
| `hive-site.xml` | Runtime-generated output of `envsubst` on the template — not a usable config on its own |
| `entrypoint-wrapper.sh` | Pre-flight script: loads secrets, runs `envsubst`, waits for PostgreSQL, then delegates to the upstream Hive entrypoint |
| `Dockerfile` | Adds PostgreSQL JDBC driver, Hadoop S3A JARs, and `gettext-base` (`envsubst`) to the upstream `apache/hive:4.0.0` image |

### Warehouse Location

Default managed table warehouse: `s3a://rideshare-silver/warehouse/`

External tables (registered by `bronze-ingestion`) point to their own S3 paths and are not subject to this default.

### Docker Profile

This service runs under the `data-pipeline` profile:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d hive-metastore
```

## Common Tasks

### Verify the Thrift server is accepting connections

```bash
docker exec rideshare-hive-metastore bash -c "echo > /dev/tcp/localhost/9083" && echo "Thrift port open"
```

### Check startup logs

```bash
docker logs rideshare-hive-metastore --tail 50
```

### Confirm secrets were loaded and hive-site.xml was generated

```bash
docker exec rideshare-hive-metastore cat /opt/hive/conf/hive-site.xml
```

The output should show real credential values, not `${POSTGRES_METASTORE_USER}` placeholders. If placeholders remain, the secrets volume was not mounted or `secrets-init` did not complete.

### List registered metastore databases (from Trino)

```bash
docker exec rideshare-trino trino --execute "SHOW SCHEMAS FROM delta"
```

### List registered tables

```bash
docker exec rideshare-trino trino --execute "SHOW TABLES FROM delta.silver"
docker exec rideshare-trino trino --execute "SHOW TABLES FROM delta.gold"
```

### Rebuild the image after Dockerfile changes

```bash
docker compose -f infrastructure/docker/compose.yml build hive-metastore
```

## Prerequisites

- `secrets-init` must complete successfully before this service starts (provides `/secrets/data-pipeline.env`)
- `postgres-metastore` must pass its healthcheck (TCP port 5432 accepting connections)
- `minio` must pass its healthcheck (S3A warehouse path resolution requires object storage to be reachable)

## Troubleshooting

### Container exits immediately on startup

The upstream `apache/hive:4.0.0` entrypoint exits if PostgreSQL is unreachable. `entrypoint-wrapper.sh` mitigates this with up to 30 TCP retries (2s interval = 60s total). If the container still exits, check:

1. `postgres-metastore` health: `docker ps | grep postgres-metastore`
2. Secrets volume: `docker exec rideshare-hive-metastore ls /secrets/`
3. Network: `docker exec rideshare-hive-metastore bash -c "echo > /dev/tcp/postgres-metastore/5432"`

### `${POSTGRES_METASTORE_USER}` appears literally in hive-site.xml

`envsubst` runs after sourcing `/secrets/data-pipeline.env`. If the secrets file is missing or empty, variables will not be substituted. Verify `secrets-init` completed: `docker ps -a | grep secrets-init`.

### Trino cannot connect to metastore

Confirm the Thrift port is open and the service is healthy:

```bash
docker inspect rideshare-hive-metastore --format '{{.State.Health.Status}}'
```

Trino's healthcheck depends on `hive-metastore` being healthy before it starts. If Trino started before the metastore was ready, restart Trino: `docker restart rideshare-trino`.

### S3A / MinIO connection errors in logs

`fs.s3a.path.style.access=true` and `fs.s3a.connection.ssl.enabled=false` are required for MinIO. If deploying against AWS S3 (production), these settings must be removed or overridden — AWS requires virtual-hosted-style URLs and TLS.

### AWS SDK / EKS Pod Identity errors in production

The Dockerfile pins `aws-java-sdk-bundle` to 1.12.780. Versions below 1.12.746 do not support the EKS Pod Identity credential endpoint. Do not downgrade this dependency.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this module
- [services/trino/README.md](../trino/README.md) — Trino query engine that consumes this metastore
- [services/postgres-metastore/README.md](../postgres-metastore/README.md) — PostgreSQL backend storing the metastore schema
- [infrastructure/docker/README.md](../../infrastructure/docker/README.md) — Full compose file reference and profiles
