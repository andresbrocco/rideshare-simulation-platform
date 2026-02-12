# Trino Configuration

Trino 439 distributed SQL query engine for interactive analytics over Delta Lake tables.

## Purpose

This directory contains Trino server configuration:
- `etc/config.properties` — Coordinator and HTTP server settings
- `etc/jvm.config` — JVM flags (heap size, GC tuning)
- `etc/node.properties` — Node identity and data directory
- `etc/catalog/delta.properties` — Delta Lake connector (Hive Metastore + MinIO)

## Configuration

| Setting | Value |
|---------|-------|
| **Image** | `trinodb/trino:439` |
| **Port** | `8084` (host) -> `8080` (container) |
| **Memory Limit** | 2GB |
| **CPU Limit** | 2.0 |
| **JVM Heap** | 1GB (`-Xmx1G`) |
| **Mode** | Single-node coordinator |
| **Container Name** | `rideshare-trino` |
| **Profile** | `data-pipeline` |

## Usage

### Start Trino

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d trino
```

### Health Check

```bash
curl http://localhost:8084/v1/info
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs trino
```

### List Catalogs

```bash
docker exec rideshare-trino trino --execute "SHOW CATALOGS"
```

### List Tables

```bash
docker exec rideshare-trino trino --catalog delta --schema default --execute "SHOW TABLES"
```

### Run a Query

```bash
docker exec rideshare-trino trino --catalog delta --schema default --execute "SELECT * FROM trips LIMIT 10"
```

### Trino Web UI

Open http://localhost:8084 in a browser to access the Trino Web UI for monitoring active queries and cluster status.

## Troubleshooting

### Queries fail with "catalog not found"

Verify the Hive Metastore is healthy and reachable:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline ps hive-metastore
docker exec rideshare-hive-metastore bash -c 'echo > /dev/tcp/localhost/9083'
```

### Queries fail with S3 errors

Check that MinIO is accessible and the required buckets exist:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline ps minio
curl http://localhost:9000/minio/health/live
```

### Trino starts but shows no tables

Tables are registered by the `bronze-init` service (via Trino) and populated by the bronze ingestion service and DBT transformations. Ensure the data pipeline has run at least once:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs bronze-ingestion
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs bronze-init
```

Note: If you need Spark Thrift Server for dual-engine DBT testing, use the `spark-testing` profile.

### Out of memory errors

Trino is limited to 2GB by Docker Compose and 1GB JVM heap. For large queries, check memory usage:

```bash
curl http://localhost:8084/v1/cluster/memory
```

## References

- [Trino 439 Documentation](https://trino.io/docs/439/)
- [Trino Delta Lake Connector](https://trino.io/docs/439/connector/delta-lake.html)
- [Trino Docker Deployment](https://trino.io/docs/439/installation/containers.html)
