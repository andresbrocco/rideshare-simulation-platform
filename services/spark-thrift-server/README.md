# Spark Thrift Server

> Apache Spark 4.0 Thrift Server for dual-engine DBT validation (optional)

## Quick Reference

| Property | Value |
|----------|-------|
| Service | `spark-thrift-server` |
| Image | `apache/spark:4.0.0-python3` |
| Profile | `spark-testing` (optional) |
| Memory Limit | 3072MB |

### Ports

| Port (Host:Container) | Purpose |
|------------------------|---------|
| `10000:10000` | JDBC/ODBC (Thrift) |
| `4041:4040` | Spark UI |

### Dependencies

| Service | Purpose |
|---------|---------|
| `openldap` | LDAP authentication for JDBC connections |
| `hive-metastore` | Table/partition catalog |
| `minio-init` | S3-compatible storage for Delta Lake |
| `secrets-init` | MinIO credentials injection |

## Common Tasks

### Start Service

The Spark Thrift Server requires the `data-pipeline` profile dependencies plus its own profile:

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile data-pipeline --profile spark-testing up -d spark-thrift-server
```

### Check Health

```bash
docker compose -f infrastructure/docker/compose.yml ps spark-thrift-server
docker compose -f infrastructure/docker/compose.yml logs spark-thrift-server
```

### Connect via Beeline

```bash
docker compose -f infrastructure/docker/compose.yml exec spark-thrift-server \
  /opt/spark/bin/beeline -u 'jdbc:hive2://localhost:10000/default' -n admin -p admin
```

### Access Spark UI

Open http://localhost:4041 in a browser to monitor active queries, stages, and executors.

### Run DBT Against Spark

The Airflow scheduler is pre-configured to use the Spark Thrift Server when available:

```bash
# Check DBT Spark connection from Airflow
docker compose -f infrastructure/docker/compose.yml exec airflow-scheduler \
  dbt debug --target spark --project-dir /opt/dbt
```

## Prerequisites

- Docker with Compose V2
- `data-pipeline` profile services running (Hive Metastore, MinIO, OpenLDAP)
- 3GB available memory

## Troubleshooting

### Service Won't Start

Spark initialization takes up to 90 seconds. Check logs for JVM errors:

```bash
docker compose -f infrastructure/docker/compose.yml logs --tail=50 spark-thrift-server
```

### JDBC Connection Refused

Verify the service is healthy (Beeline health check must pass):

```bash
docker compose -f infrastructure/docker/compose.yml ps spark-thrift-server
```

### Authentication Failure

LDAP auth requires the `openldap` service. Check it's running and healthy:

```bash
docker compose -f infrastructure/docker/compose.yml ps openldap
```

Default credentials: `admin` / `admin`

### Tables Not Visible

Ensure Hive Metastore is healthy and Delta tables have been registered:

```bash
docker compose -f infrastructure/docker/compose.yml ps hive-metastore
docker compose -f infrastructure/docker/compose.yml logs delta-table-init
```

## Related

- [CONTEXT.md](CONTEXT.md) -- Architecture and responsibility boundaries
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) -- Service definition
- [../hive-metastore/CONTEXT.md](../hive-metastore/CONTEXT.md) -- Catalog service
- [../../tools/dbt/CONTEXT.md](../../tools/dbt/CONTEXT.md) -- DBT project
