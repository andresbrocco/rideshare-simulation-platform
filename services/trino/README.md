# Trino

> Distributed SQL query engine providing analytical access to Delta Lake tables (Bronze, Silver, Gold) stored in MinIO via the Hive Metastore catalog.

## Quick Reference

### Ports

| Host Port | Container Port | Protocol | Description |
|-----------|---------------|----------|-------------|
| `8084` | `8080` | HTTP | Trino coordinator UI and query API |

### Environment Variables

Credentials are not passed as Docker environment variables. The entrypoint sources `/secrets/data-pipeline.env` (written by the `secrets-init` sidecar) and uses those values to render `delta.properties` at startup.

| Variable | Source | Used In |
|----------|--------|---------|
| `MINIO_ROOT_USER` | `/secrets/data-pipeline.env` | `delta.properties` — MinIO S3 access key |
| `MINIO_ROOT_PASSWORD` | `/secrets/data-pipeline.env` | `delta.properties` — MinIO S3 secret key |
| `TRINO_ADMIN_PASSWORD_HASH` | Container environment / secrets | `password.db` — bcrypt hash for the `admin` Trino account |
| `TRINO_VISITOR_PASSWORD_HASH` | Container environment / secrets | `password.db` — bcrypt hash for the `visitor` Trino account |
| `TRINO_ENVIRONMENT` | Docker compose environment | Node environment label (set to `docker`) |
| `TRINO_HOST` | `delta-table-init` container env | Registration script target host |
| `TRINO_PORT` | `delta-table-init` container env | Registration script target port |

### Configuration Files

| File | Purpose |
|------|---------|
| `etc/config.properties` | Coordinator settings — HTTP port 8080, single-node mode |
| `etc/jvm.config` | JVM options — 1 GB heap (`-Xmx1G`), G1GC |
| `etc/node.properties` | Node identity — environment label, data directory |
| `etc/catalog/delta.properties.template` | Delta Lake catalog template with `${MINIO_ROOT_USER}` / `${MINIO_ROOT_PASSWORD}` placeholders |
| `etc/catalog/delta.properties` | Dev-time rendered catalog file with placeholder credentials — **not used at runtime** (entrypoint renders a fresh copy) |
| `etc/password.db.template` | Password database template with `${TRINO_ADMIN_PASSWORD_HASH}` / `${TRINO_VISITOR_PASSWORD_HASH}` placeholders |
| `etc/password-authenticator.properties` | Configures FILE-based authenticator pointing at `/tmp/trino-etc/password.db` with a 5s refresh period |
| `entrypoint.sh` | Custom startup: copies config to `/tmp/trino-etc`, renders `delta.properties` and `password.db` from templates, launches Trino launcher |

### Catalog

The single catalog is named `delta`, backed by the `delta_lake` connector.

| Setting | Value |
|---------|-------|
| Connector | `delta_lake` |
| Hive Metastore URI | `thrift://hive-metastore:9083` |
| S3 endpoint | `http://minio:9000` (path-style access) |
| Register table procedure | Enabled (`delta.register-table-procedure.enabled=true`) |
| Non-concurrent writes | Enabled |

### Docker Profile

```
data-pipeline
```

Start Trino (and all data-pipeline dependencies):

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile data-pipeline up -d trino
```

### Resource Limits

| Resource | Limit |
|----------|-------|
| Container memory | 2 GB |
| JVM heap (`-Xmx`) | 1 GB |

Do not increase the heap above 1.5 GB — the container memory limit leaves headroom for off-heap buffers.

---

## Registered Tables

Tables are registered by the `delta-table-init` one-shot container (`infrastructure/scripts/register-delta-tables.sh`) after Trino is healthy.

### Schemas and S3 Buckets

| Schema | S3 Bucket |
|--------|-----------|
| `delta.bronze` | `s3a://rideshare-bronze/` |
| `delta.silver` | `s3a://rideshare-silver/` |
| `delta.gold` | `s3a://rideshare-gold/` |

### Bronze Tables (`delta.bronze`)

`bronze_gps_pings`, `bronze_trips`, `bronze_driver_status`, `bronze_surge_updates`, `bronze_ratings`, `bronze_payments`, `bronze_driver_profiles`, `bronze_rider_profiles`

### DLQ Tables (`delta.bronze`)

`dlq_bronze_gps_pings`, `dlq_bronze_trips`, `dlq_bronze_driver_status`, `dlq_bronze_surge_updates`, `dlq_bronze_ratings`, `dlq_bronze_payments`, `dlq_bronze_driver_profiles`, `dlq_bronze_rider_profiles`

### Silver Tables (`delta.silver`)

`stg_trips`, `stg_gps_pings`, `stg_driver_status`, `stg_surge_updates`, `stg_ratings`, `stg_payments`, `stg_drivers`, `stg_riders`, `anomalies_all`, `anomalies_gps_outliers`, `anomalies_impossible_speeds`, `anomalies_zombie_drivers`

### Gold Tables (`delta.gold`)

`fact_trips`, `fact_payments`, `fact_ratings`, `fact_cancellations`, `fact_driver_activity`, `dim_drivers`, `dim_riders`, `dim_zones`, `dim_time`, `dim_payment_methods`, `agg_hourly_zone_demand`, `agg_daily_driver_performance`, `agg_daily_platform_revenue`, `agg_surge_history`

---

## Common Tasks

### Open the Trino UI

```
http://localhost:8084
```

Log in with the `admin` or `visitor` credentials (passwords set via `TRINO_ADMIN_PASSWORD_HASH` / `TRINO_VISITOR_PASSWORD_HASH`).

### Run a query via Trino CLI

```bash
docker exec -it rideshare-trino trino \
  --server http://localhost:8080 \
  --catalog delta \
  --schema gold \
  --execute "SELECT count(*) FROM fact_trips"
```

### Run a query via curl (HTTP API)

```bash
curl -s -X POST http://localhost:8084/v1/statement \
  -H "X-Trino-User: dev" \
  -H "X-Trino-Catalog: delta" \
  -H "X-Trino-Schema: gold" \
  -H "Content-Type: application/json" \
  -d "SELECT count(*) FROM fact_trips"
```

### List all registered tables

```bash
docker exec -it rideshare-trino trino \
  --server http://localhost:8080 \
  --catalog delta \
  --execute "SHOW TABLES IN bronze"
```

### Re-run table registration (after new data arrives)

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile data-pipeline restart delta-table-init
```

Or run the registration script directly inside the Trino container:

```bash
docker exec rideshare-trino \
  /bin/bash /opt/init-scripts/register-delta-tables.sh
```

### Register a single table manually

```bash
docker exec -it rideshare-trino trino \
  --server http://localhost:8080 \
  --execute "CALL delta.system.register_table(
    schema_name => 'gold',
    table_name  => 'fact_trips',
    table_location => 's3a://rideshare-gold/fact_trips/'
  )"
```

---

## Troubleshooting

### Trino fails to start — config not writable

**Symptom:** Container exits immediately with a permission error on `/etc/trino`.

**Cause:** On Linux CI runners, bind-mounted files may be owned by a different UID than the Trino user (UID 1000).

**Fix:** The `entrypoint.sh` copies `/etc/trino` to `/tmp/trino-etc` before use. If the entrypoint is not being called, verify the compose service uses `entrypoint: ["/custom-entrypoint.sh"]`.

### `delta.properties` contains placeholder credentials

**Symptom:** Trino logs show S3 authentication errors with `${MINIO_ROOT_USER}` literally in the config.

**Cause:** The `secrets-init` container did not complete successfully, or `/secrets/data-pipeline.env` is missing.

**Fix:**
```bash
docker logs rideshare-secrets-init
# Verify the secrets volume is populated:
docker exec rideshare-trino cat /secrets/data-pipeline.env
```

### Tables not visible after startup

**Symptom:** `SHOW TABLES IN bronze` returns empty even though MinIO has data.

**Cause:** The `delta-table-init` container runs once at startup. If data was written after that run, tables won't be registered.

**Fix:** Restart the init container to re-run registration:
```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile data-pipeline restart delta-table-init
```

### Query fails with "Table not found" for Silver/Gold tables

**Symptom:** Gold or Silver tables return "Table not found" in Trino.

**Cause:** DBT views (`materialized='view'`) cannot be registered as Delta tables. Only materialized Delta exports (written by `export-dbt-to-s3.py`) are registered.

**Fix:** Confirm the Airflow DBT DAGs have completed and the export step has run. Check `rideshare-silver` and `rideshare-gold` MinIO buckets for `_delta_log` directories.

### Authentication fails — "Authentication failed" on login

**Symptom:** Trino UI or CLI rejects credentials even with the correct password.

**Cause:** `TRINO_ADMIN_PASSWORD_HASH` or `TRINO_VISITOR_PASSWORD_HASH` was not set, is empty, or contains a malformed bcrypt hash. The entrypoint renders `password.db` from the template at startup using `envsubst`/`sed` — an unset variable produces a literal empty string in the file.

**Fix:**
```bash
# Inspect the rendered password file inside the container:
docker exec rideshare-trino cat /tmp/trino-etc/password.db
# Regenerate a bcrypt hash (cost factor 10):
htpasswd -bnBC 10 "" <plaintext_password> | tr -d ':\n' | sed 's/$2y/$2b/'
# Then restart Trino after setting the corrected hash in the secrets source.
```

### Out of memory errors

**Symptom:** Trino query fails with `ExitOnOutOfMemoryError` or container OOM-killed.

**Cause:** Heap is capped at 1 GB (`-Xmx1G`). Large analytical queries over unpartitioned Bronze tables can exceed this.

**Fix:** Add a `LIMIT` clause during development. Do not increase heap above 1.5 GB without also raising the container memory limit above 2 GB.

---

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, non-obvious implementation details
- [services/hive-metastore/README.md](../hive-metastore/README.md) — Metadata catalog Trino depends on
- [services/grafana/README.md](../grafana/README.md) — Grafana uses Trino as a datasource (plugin: `trino-datasource`, port 8084)
- [infrastructure/scripts/register-delta-tables.sh](../../infrastructure/scripts/register-delta-tables.sh) — Table registration script
