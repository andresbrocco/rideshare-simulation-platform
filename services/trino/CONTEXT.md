# CONTEXT.md — Trino

## Purpose

Distributed SQL query engine (Trino 439) that provides interactive analytical queries over Delta Lake tables in the medallion lakehouse architecture. Runs in single-node coordinator mode for local development and connects to the Hive Metastore for table metadata and MinIO for data access.

## Responsibility Boundaries

- **Owns**: SQL query execution, query planning and optimization, catalog connector configuration
- **Delegates to**: Hive Metastore for table/partition metadata resolution, MinIO for data storage via S3A, Grafana for dashboard queries (via the `trino-datasource` plugin)
- **Does not handle**: Data ingestion, schema management, data transformation (Spark/dbt), metadata persistence (Hive Metastore)

## Key Concepts

**Single-Node Coordinator**: Configured with `coordinator=true` and `node-scheduler.include-coordinator=true` in `config.properties`, meaning the single Trino node acts as both coordinator and worker. Suitable for local development but not production.

**Delta Lake Connector**: The `delta.properties` catalog file configures the `delta_lake` connector, enabling Trino to read Delta Lake tables directly from MinIO. Non-concurrent writes are enabled via `delta.enable-non-concurrent-writes=true`.

**JVM Tuning**: Allocated 1GB heap (`-Xmx1G`) with G1GC collector, tuned for interactive query latency with a 32MB region size and 256MB reserved code cache.

**Resource Limits**: Docker Compose allocates 2GB memory and 2 CPUs, with a 0.25 CPU reservation to prevent starvation of other services.

## Non-Obvious Details

The `trino-datasource` plugin in Grafana connects to Trino's HTTP API on port 8080 (internal container port), not a PostgreSQL wire protocol. The `format` field in Grafana dashboard JSON for Trino queries must be numeric (`0` for table, `1` for time_series), not string values.

The host port mapping is `8084:8080` to avoid conflicts with other services that use port 8080 (such as the MinIO console or Airflow).

Trino depends on both `hive-metastore` and `minio` being healthy before starting. If the metastore is unreachable, Trino will start but queries against the `delta` catalog will fail.

## Related Modules

- **[services/hive-metastore](../hive-metastore/CONTEXT.md)** — Provides table metadata via Thrift; Trino's Delta Lake connector requires it
- **[tools/dbt](../../tools/dbt/CONTEXT.md)** — Runs SQL transformations through Trino for the Silver and Gold layers
- **[services/grafana](../grafana/CONTEXT.md)** — Queries Trino via the `trino-datasource` plugin for analytical dashboards
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Trino container, resource limits, and volume mounts
