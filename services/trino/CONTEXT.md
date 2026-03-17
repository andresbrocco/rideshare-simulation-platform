# CONTEXT.md — Trino

## Purpose

Configuration and startup scripting for the Trino SQL query engine, which provides distributed SQL access to Delta Lake tables stored in MinIO. Trino is the query layer used by Grafana dashboards and Trino CLI consumers to run analytical queries over the medallion lakehouse (Bronze, Silver, Gold layers).

## Responsibility Boundaries

- **Owns**: Trino server configuration (`etc/`), the custom entrypoint script, the Delta Lake catalog definition, and the FILE-based password database (`password.db.template` → rendered `password.db`)
- **Delegates to**: Hive Metastore (table/schema metadata via Thrift at port 9083), MinIO (underlying S3-compatible object storage), `secrets-init` sidecar (credential provisioning)
- **Does not handle**: Table registration (done by `delta-table-init` container via `register-delta-tables.sh`), data ingestion, or query routing between services

## Key Concepts

- **Delta Lake connector**: The single catalog (`delta`) uses the `delta_lake` connector, which requires both a Hive Metastore (for schema metadata) and S3-compatible storage (MinIO) for the actual Parquet+Delta log files.
- **`delta.register-table-procedure.enabled=true`**: Enables the `system.register_table()` stored procedure, which is how the `delta-table-init` job registers existing Delta tables that were created outside Trino (e.g., by the bronze-ingestion Spark/Delta writer).
- **Single-node coordinator**: `coordinator=true` with `node-scheduler.include-coordinator=true` means the coordinator also acts as a worker. There are no separate worker nodes in this deployment.
- **FILE-based password authentication**: `password-authenticator.properties` configures the `file` authenticator pointing at `/tmp/trino-etc/password.db`. Only the `admin` account is defined (full access). The admin bcrypt hash is computed at container startup from the `ADMIN_PASSWORD` in the `data-pipeline` secret (via `bcrypt` in Docker dev, via `htpasswd` in K8s).

## Non-Obvious Details

- **Bind-mount write workaround**: The entrypoint copies `/etc/trino` to `/tmp/trino-etc` before use. On Linux CI runners, the bind-mounted config directory may be owned by a different UID than the Trino user (UID 1000), making it non-writable. The copy sidesteps this permission issue.
- **Credential injection at startup**: MinIO credentials are not baked into the image or compose environment. The entrypoint sources `/secrets/data-pipeline.env` (written by `secrets-init`) and uses `envsubst` (falling back to `sed`) to render `delta.properties.template` into `delta.properties` at container start. The committed `etc/catalog/delta.properties` file contains placeholder credentials (`admin`/`adminadmin`) and is a dev-time artifact — the rendered file in `/tmp/trino-etc/catalog/delta.properties` is what Trino actually reads. For `password.db`, the admin bcrypt hash is computed at startup from `ADMIN_PASSWORD` (via `bcrypt` in Docker dev, via `htpasswd` in K8s) and written with `chmod 600`.
- **Memory cap**: JVM heap is set to `-Xmx1G` while the compose service has a 2 GB container memory limit, leaving headroom for off-heap buffers. Increasing the heap above 1.5 GB risks OOM kills.
- **Port mapping**: Trino listens on container port 8080 but is exposed on host port 8084 to avoid conflicts with other services.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana](../grafana/CONTEXT.md) — Reverse dependency — Provides dashboards/monitoring/simulation-metrics.json, dashboards/data-engineering/data-ingestion.json, dashboards/data-engineering/data-quality.json (+10 more)
- [services/grafana/provisioning](../grafana/provisioning/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/provisioning/datasources](../grafana/provisioning/datasources/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/hive-metastore](../hive-metastore/CONTEXT.md) — Dependency — Hive Metastore service providing table metadata catalog for Delta Lake tables, c...
