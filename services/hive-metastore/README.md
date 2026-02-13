# Hive Metastore

> Apache Hive 4.0.0 Metastore service that stores table and partition metadata for Delta Lake tables in the medallion lakehouse architecture.

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 9083 | Thrift | Hive Metastore API |

### Environment Variables

Configuration is injected at runtime from **LocalStack Secrets Manager** via the `secrets-init` service. Credentials are sourced from `/secrets/data-pipeline.env`.

| Variable | Purpose | Template Usage |
|----------|---------|----------------|
| `POSTGRES_METASTORE_USER` | PostgreSQL username for metastore backend | `hive-site.xml.template` substitution |
| `POSTGRES_METASTORE_PASSWORD` | PostgreSQL password for metastore backend | `hive-site.xml.template` substitution |
| `MINIO_ROOT_USER` | MinIO access key for S3A filesystem | `hive-site.xml.template` substitution |
| `MINIO_ROOT_PASSWORD` | MinIO secret key for S3A filesystem | `hive-site.xml.template` substitution |
| `DB_HOST` | PostgreSQL hostname | Default: `postgres-metastore` |
| `DB_PORT` | PostgreSQL port | Default: `5432` |

**Local Development Defaults:**
- All credentials use `admin` for username/password
- Configured in `rideshare/hive-thrift` and `rideshare/minio` secrets in LocalStack

### Configuration Files

| File | Purpose |
|------|---------|
| `hive-site.xml.template` | Template for Hive configuration (env vars substituted at runtime) |
| `hive-site.xml` | Generated configuration file (created by `entrypoint-wrapper.sh`) |
| `entrypoint-wrapper.sh` | Custom entrypoint that waits for PostgreSQL, substitutes env vars, then runs Hive |
| `Dockerfile` | Adds PostgreSQL JDBC driver and S3A filesystem JARs to base image |

### Dependencies

**Runtime:**
- `postgres-metastore` (port 5432) - Catalog persistence backend
- `minio` (port 9000) - S3-compatible storage for warehouse data
- `secrets-init` - Injects credentials from LocalStack Secrets Manager

**Downstream Clients:**
- `trino` - Queries Delta Lake tables via Thrift connection
- `spark-thrift-server` - Dual-engine validation for DBT models
- `delta-table-init` - Registers Delta Lake tables via Trino

### Docker Service

**Profile:** `data-pipeline`

```bash
# Start with data pipeline services
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f hive-metastore

# Check health
docker compose -f infrastructure/docker/compose.yml ps hive-metastore
```

## Configuration Details

### PostgreSQL Backend

The metastore catalog is persisted in PostgreSQL instead of the default Derby database:

- **Database:** `metastore` on `postgres-metastore:5432`
- **JDBC Driver:** `postgresql-42.7.4.jar` (added via Dockerfile)
- **Schema Initialization:** Runs automatically on first startup via Hive's `schematool -initSchema`

### S3A Filesystem

Hive connects to MinIO using the S3A filesystem implementation:

- **Endpoint:** `http://minio:9000`
- **Path Style Access:** Enabled (required for MinIO)
- **SSL:** Disabled (local development)
- **Warehouse Directory:** `s3a://rideshare-silver/warehouse/`
- **Required JARs:** `hadoop-aws-3.3.6.jar`, `aws-java-sdk-bundle-1.12.367.jar` (copied from Hadoop tools lib)

### Thrift API

Clients connect to the metastore via Thrift protocol:

- **URI:** `thrift://hive-metastore:9083`
- **Clients:** Trino (`delta` catalog connector), Spark Thrift Server
- **No Authentication:** Open access within Docker network

## Common Tasks

### Check Metastore Health

```bash
# TCP socket test (same as health check)
docker exec rideshare-hive-metastore bash -c 'echo > /dev/tcp/localhost/9083'

# View initialization logs
docker compose -f infrastructure/docker/compose.yml logs hive-metastore | grep -i schema
```

### Verify PostgreSQL Backend Connection

```bash
# Connect to metastore database
docker exec -it rideshare-postgres-metastore psql -U admin -d metastore

# List tables (should see Hive catalog tables)
\dt
```

Expected tables:
- `TBLS` (table definitions)
- `PARTITIONS` (partition metadata)
- `SDS` (storage descriptors)
- `COLUMNS_V2` (column schemas)

### Verify S3A Filesystem Configuration

```bash
# Check hive-site.xml was generated correctly
docker exec rideshare-hive-metastore cat /opt/hive/conf/hive-site.xml

# Verify environment variables were substituted
docker exec rideshare-hive-metastore cat /opt/hive/conf/hive-site.xml | grep -A1 "fs.s3a.access.key"
```

### Test Thrift Connection from Trino

```bash
# Connect to Trino and list Delta Lake tables
docker exec -it rideshare-trino trino --catalog delta --schema default

# In Trino CLI:
SHOW TABLES;
```

### Reinitialize Metastore Schema

```bash
# Drop metastore database
docker exec -it rideshare-postgres-metastore psql -U admin -c "DROP DATABASE metastore;"
docker exec -it rideshare-postgres-metastore psql -U admin -c "CREATE DATABASE metastore;"

# Restart metastore (schema will reinitialize)
docker compose -f infrastructure/docker/compose.yml restart hive-metastore
```

## Troubleshooting

### Issue: Metastore Fails to Start with "Connection Refused" Error

**Cause:** PostgreSQL backend not ready when metastore starts.

**Solution:** The `entrypoint-wrapper.sh` script waits up to 60 seconds for PostgreSQL. Check if `postgres-metastore` is healthy:

```bash
docker compose -f infrastructure/docker/compose.yml ps postgres-metastore

# View PostgreSQL logs
docker compose -f infrastructure/docker/compose.yml logs postgres-metastore
```

### Issue: Trino Cannot Connect to Hive Metastore

**Symptom:** Trino catalog queries fail with `Hive metastore is not available`.

**Diagnosis:**

```bash
# Check Thrift port is listening
docker exec rideshare-hive-metastore netstat -tuln | grep 9083

# Test TCP connection from Trino container
docker exec rideshare-trino bash -c 'echo > /dev/tcp/hive-metastore/9083'
```

**Solution:** Restart metastore and check logs for Thrift binding errors.

### Issue: S3A Filesystem Errors (MinIO Connection Failed)

**Symptom:** Queries fail with `NoSuchBucket` or `Connection refused` to MinIO.

**Diagnosis:**

```bash
# Check MinIO is healthy
docker compose -f infrastructure/docker/compose.yml ps minio

# Verify S3A configuration in hive-site.xml
docker exec rideshare-hive-metastore cat /opt/hive/conf/hive-site.xml | grep -A2 "fs.s3a.endpoint"

# Test MinIO connectivity from metastore container
docker exec rideshare-hive-metastore curl -v http://minio:9000/minio/health/live
```

**Solution:** Ensure `minio` service is running and buckets are initialized (check `minio-init` logs).

### Issue: Environment Variables Not Substituted in hive-site.xml

**Symptom:** Configuration contains `${POSTGRES_METASTORE_USER}` literal strings instead of actual credentials.

**Diagnosis:**

```bash
# Check if entrypoint-wrapper.sh ran successfully
docker compose -f infrastructure/docker/compose.yml logs hive-metastore | grep "Substituting environment variables"

# Verify secrets volume is mounted
docker exec rideshare-hive-metastore cat /secrets/data-pipeline.env
```

**Solution:** Ensure `secrets-init` service completed successfully and `/secrets/data-pipeline.env` exists.

### Issue: Schema Initialization Fails

**Symptom:** Metastore logs show `Failed to initialize schema` errors.

**Diagnosis:**

```bash
# Check PostgreSQL JDBC driver is in classpath
docker exec rideshare-hive-metastore ls -lh /opt/hive/lib/postgresql-42.7.4.jar

# Verify PostgreSQL database exists
docker exec rideshare-postgres-metastore psql -U admin -l
```

**Solution:** Ensure `postgres-metastore` has `metastore` database created. If not, create it manually:

```bash
docker exec -it rideshare-postgres-metastore psql -U admin -c "CREATE DATABASE metastore;"
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture details and non-obvious implementation notes
- [services/trino/](../trino/) - Query engine that uses this metastore
- [infrastructure/scripts/register-delta-tables.sh](../../infrastructure/scripts/register-delta-tables.sh) - Delta Lake table registration
- [tools/dbt/](../../tools/dbt/) - DBT models using dual-engine validation (Trino + Spark Thrift Server)
