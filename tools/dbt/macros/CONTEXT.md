# CONTEXT.md — Macros

## Purpose

Provides reusable dbt Jinja macros that abstract adapter differences (DuckDB vs Spark/Glue), handle Delta Lake edge cases during early pipeline stages, and enforce schema naming conventions for the medallion lakehouse layers.

## Responsibility Boundaries

- **Owns**: Adapter dispatch logic for cross-engine SQL compatibility, Bronze Delta table access abstraction, empty-table schema safety, schema-to-database name mapping for dbt-spark
- **Delegates to**: `cross_db/` subdirectory for individual cross-engine SQL function implementations (date/time, JSON extraction, array access, string splitting)
- **Does not handle**: Model business logic, incremental watermark logic (that stays in models), or Trino/query-layer concerns

## Key Concepts

**Adapter dispatch (`delta_source`)**: dbt's `adapter.dispatch()` pattern routes macro calls to adapter-specific implementations. `duckdb__delta_source` uses `delta_scan('s3://...')` to read Delta directly from S3; `spark__delta_source` and `glue__delta_source` use Hive Metastore catalog references (`bronze.table_name`). The `BRONZE_BUCKET` env var overrides the default S3 bucket for DuckDB.

**Empty Delta table guard (`source_with_empty_guard`)**: When a Bronze Delta table exists but has no rows, Spark raises `DELTA_READ_TABLE_WITHOUT_COLUMNS`. The macro uses a `UNION ALL` with a `WHERE 1=0` typed-null branch to force schema inference even on empty tables. Callers must pass an explicit `columns` dict mapping column names to Spark type strings.

**Schema name override (`generate_schema_name`)**: dbt-spark treats "schema" as the Hive database name. This macro bypasses dbt's default `<target_schema>_<custom_schema>` concatenation and returns `custom_schema_name` directly, so staging models resolve to the `silver` database and gold models to the `gold` database without environment-name prefixes.

## Non-Obvious Details

- `generate_schema_name` intentionally discards `target.schema` when a `custom_schema_name` is set. This is the opposite of dbt's default behaviour and is required for clean `silver.*` / `gold.*` table references in Trino.
- `source_with_empty_guard` delegates Bronze path resolution to `delta_source` internally, so adapters are handled in one place; staging models should call `source_with_empty_guard` rather than `delta_source` directly.
- `glue__delta_source` simply aliases `spark__delta_source`, reflecting that AWS Glue uses the same Hive Metastore catalog interface as local Spark.
- The `BRONZE_BUCKET` env var is only consumed by the DuckDB adapter path; Spark/Glue resolve the bucket via the Hive Metastore and do not read this variable.

## Related Modules

- [tools/dbt](../CONTEXT.md) — Shares DBT Transformations domain (generate_schema_name override)
- [tools/dbt/macros/cross_db](cross_db/CONTEXT.md) — Shares DBT Transformations domain (adapter.dispatch)
- [tools/dbt/models](../models/CONTEXT.md) — Reverse dependency — Provides stg_trips, stg_gps_pings, stg_driver_status (+24 more)
