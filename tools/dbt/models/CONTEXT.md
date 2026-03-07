# CONTEXT.md — Models

## Purpose

Implements the Silver and Gold layers of the medallion lakehouse pipeline using dbt. Transforms raw Bronze Kafka events (stored as Delta files in MinIO/S3) into a cleaned Silver staging layer and then into a star schema Gold layer optimized for analytics via Trino SQL.

## Responsibility Boundaries

- **Owns**: All SQL transformation logic from Bronze source tables through staging, dimensions, facts, and aggregates; schema tests and data quality contracts; anomaly detection models
- **Delegates to**: `tools/dbt/macros/` for cross-adapter SQL abstractions (`delta_source()`, `json_field()`, `to_ts()`, `epoch_seconds()`); `tools/dbt/tests/` for custom generic test implementations; `tools/dbt/seeds/` for static reference data (zones)
- **Does not handle**: Raw data ingestion into Bronze (owned by `services/bronze-ingestion`); orchestration scheduling (owned by `services/airflow`); Great Expectations validation (owned by `tools/great-expectations`); Trino table registration (handled by `bronze-init` scripts)

## Key Concepts

**Staging (Silver) layer** — `models/staging/`: Incremental dbt models that parse raw JSON from the `_raw_value` column of Bronze tables, deduplicate on `event_id`, and enforce data quality rules. All staging models use `materialized='incremental'`, `unique_key='event_id'`, `incremental_strategy='merge'`, `file_format='delta'`. Watermark on `_ingested_at` drives incremental filtering.

**Marts (Gold) layer** — `models/marts/`: Three subdirectories: `dimensions/` (SCD Type 2 and current-state dims), `facts/` (transaction and activity fact tables), `aggregates/` (pre-computed rollups for dashboard performance). All dimensions and facts use `dbt_utils.generate_surrogate_key()`.

**SCD Type 2** — `dim_drivers` and `dim_payment_methods` track historical attribute changes using `lead(timestamp)` window functions to derive `valid_from`, `valid_to`, and `current_flag`. Surrogate key includes both natural key and `valid_from`. Custom test `scd_validity` enforces non-overlapping validity periods.

**Anomaly detection models** — Four views under `staging/` (`anomalies_gps_outliers`, `anomalies_impossible_speeds`, `anomalies_zombie_drivers`, `anomalies_all`) that flag data quality issues for monitoring. These are `materialized='view'` and are not registered as Trino Delta tables.

**Cross-adapter macro dispatch** — The `delta_source()` macro dispatches between DuckDB (direct S3 Delta scan) and Spark/Glue (Hive Metastore catalog reference) so the same SQL works in both environments.

**Test data models** — `models/test_data/` contains SQL fixtures that synthesize Bronze-format data for use in testing without requiring live Kafka ingestion.

## Non-Obvious Details

- **Anomaly views cannot be registered as Trino Delta tables.** `anomalies_gps_outliers` and `anomalies_zombie_drivers` use `materialized='view'`, which produces no transaction log. The Trino registration script (`register-trino-tables.py`) skips them. Only incremental/table materializations produce registerable Delta files.
- **`fact_trips.distance_km` is a null placeholder.** The column is defined as `cast(null as double)` — distance calculation from pickup/dropoff coordinates has not been implemented.
- **`stg_ratings` and `stg_payments` can have zero rows** early in a simulation session because trips must reach the `completed` state before ratings and payments are emitted. Tests that check row counts will pass vacuously on empty tables.
- **`agg_daily_driver_performance.online_minutes`** represents total logged-in time (sum of all driver statuses including `available`, `en_route_pickup`, `on_trip`, `driving_closer_to_home`) — not just idle online time. The test `en_route + on_trip <= online_minutes` depends on this definition.
- **Fact table foreign keys resolve at Gold layer.** Staging models deliberately defer `relationships` tests to the Gold layer where dimensional surrogate keys exist. Running `dbt test --select staging` will not catch referential integrity violations.
- **`fact_ratings` rater/ratee keys require conditional joins.** Ratings are bidirectional (drivers rate riders and riders rate drivers). `rater_key` and `ratee_key` both resolve to either `dim_drivers` or `dim_riders` depending on `rater_type`/`ratee_type`, so joins must be written conditionally.
- **`dim_drivers` is `materialized='table'`** (not incremental) because SCD Type 2 requires full recomputation of window functions over the entire history on each run.
- **Bronze source access is adapter-specific.** Under DuckDB the macro calls `delta_scan('s3://...')` directly; under Glue it references `bronze.{table}` via Hive Metastore. The `sources.yml` documents both access patterns in the `description` field.

## Related Modules

- [tools/dbt/macros](../macros/CONTEXT.md) — Dependency — dbt Jinja macros abstracting adapter differences, Bronze Delta table access, emp...
- [tools/dbt/seeds](../seeds/CONTEXT.md) — Dependency — Static geographic reference data for Sao Paulo's 96 administrative districts, pr...
- [tools/dbt/tests](../tests/CONTEXT.md) — Dependency — Custom singular tests for Gold layer star schema structural invariants, SCD Type...
