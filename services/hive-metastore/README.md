# Hive Metastore Configuration

Apache Hive 4.0.0 Metastore with PostgreSQL backend and S3A (MinIO) filesystem support.

## Purpose

This directory contains the Hive Metastore service configuration:
- `Dockerfile` — Custom image adding PostgreSQL JDBC driver and Hadoop AWS JARs to the base `apache/hive:4.0.0` image
- `hive-site.xml` — Metastore configuration (PostgreSQL backend, S3A/MinIO filesystem, Thrift URI)

## Configuration

| Setting | Value |
|---------|-------|
| **Image** | Custom (Dockerfile based on `apache/hive:4.0.0`) |
| **Port** | `9083` (Thrift) |
| **Memory Limit** | 512MB |
| **Catalog Backend** | PostgreSQL 16 (`postgres-metastore:5432/metastore`) |
| **Warehouse Dir** | `s3a://rideshare-silver/warehouse/` |
| **Container Name** | `rideshare-hive-metastore` |
| **Profile** | `data-pipeline` |

## Usage

### Start Hive Metastore

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d hive-metastore
```

### Health Check

```bash
docker exec rideshare-hive-metastore bash -c 'echo > /dev/tcp/localhost/9083'
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs hive-metastore
```

### Follow Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs -f hive-metastore
```

## Troubleshooting

### Metastore fails to start

Check that `postgres-metastore` is healthy first. The metastore depends on it for catalog storage:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline ps postgres-metastore
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs postgres-metastore
```

### Schema initialization errors

On first startup, the Hive entrypoint runs `schematool -initSchema` to create the catalog tables. If this fails, the most common cause is a stale PostgreSQL volume from a previous incompatible version:

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline down
docker volume rm rideshare-simulation-platform_postgres-metastore-data
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d hive-metastore
```

### S3A / MinIO connectivity errors

Verify MinIO is accessible from the metastore container:

```bash
docker exec rideshare-hive-metastore curl -s http://minio:9000/minio/health/live
```

### Long startup time

The health check has a 120-second `start_period` to accommodate schema initialization on first boot. Subsequent restarts are faster since the schema already exists.

## References

- [Apache Hive 4.0 Documentation](https://hive.apache.org/)
- [Hive Metastore Configuration Properties](https://cwiki.apache.org/confluence/display/Hive/AdminManual+Metastore+Administration)
- [Hadoop S3A Filesystem Configuration](https://hadoop.apache.org/docs/stable/hadoop-aws/tools/hadoop-aws/index.html)
