# CONTEXT.md — DBT

## Purpose

Silver and Gold transformation layer for the rideshare medallion lakehouse. Reads raw Kafka event JSON from Bronze Delta tables, parses and deduplicates into Silver staging models, then builds a star schema in Gold (dimensions, facts, aggregates) suitable for Trino SQL analytics.

## Responsibility Boundaries

- **Owns**: Bronze-to-Silver JSON parsing and deduplication, Silver-to-Gold star schema construction, anomaly detection views, cross-database SQL abstraction via macros
- **Delegates to**: Bronze ingestion service (raw event storage), Airflow (scheduling and orchestration), Trino (query serving against Gold tables), Great Expectations (data quality checks)
- **Does not handle**: Kafka consumption, Delta table registration with Trino catalogs, data quality gating (that belongs to Great Expectations)

## Key Concepts

- **Dual-target profiles**: `profiles.yml` defines two execution targets. `duckdb` reads Bronze from S3/MinIO via `delta_scan()` and stores results locally as a DuckDB file — used for local development and Airflow-orchestrated runs. `glue` executes as an AWS Glue Spark job using the Hive Metastore catalog — used for production. The active target is selected via the `DBT_TARGET` environment variable passed to Airflow.
- **Adapter-dispatched macros**: The `delta_source` macro uses `adapter.dispatch` to emit DuckDB-specific `delta_scan('s3://...')` syntax for the DuckDB target and Hive catalog references (`bronze.table_name`) for the Spark/Glue target. Cross-database helpers (`json_field`, `to_ts`, `epoch_seconds`, `split_string`, `safe_array_element`) follow the same pattern.
- **`generate_schema_name` override**: The built-in dbt macro is overridden so that `+schema: silver` and `+schema: gold` in `dbt_project.yml` map directly to database names — not `<target_schema>_silver`. This maintains clean layer separation without a name prefix on either target.
- **SCD Type 2 dimensions**: `dim_drivers` and `dim_payment_methods` use window functions (`lag`/`lead`) to derive `valid_from`, `valid_to`, and `current_flag` columns. `fact_trips` joins to `dim_drivers` with a temporal range join (`completed_at >= valid_from AND completed_at < valid_to`) to capture the driver's state at the time of the trip.
- **Event-based staging**: Bronze stores one row per Kafka event (e.g., `trip.requested`, `trip.matched`, `trip.completed`). Staging models (`stg_trips`, `stg_driver_status`) parse the `_raw_value` JSON and deduplicate by `event_id`. Fact models then pivot event rows into one row per entity lifecycle (e.g., one row per completed trip assembling timestamps from multiple event types).

## Non-Obvious Details

- **`source_with_empty_guard` macro**: Spark/Glue raises `DELTA_READ_TABLE_WITHOUT_COLUMNS` when reading a Delta table that exists but has no data yet. The macro wraps every Bronze source in a `UNION ALL` with a `WHERE 1=0` typed-null branch to prevent this error during early pipeline runs before Bronze data arrives.
- **Anomaly models are views, not tables**: `anomalies_gps_outliers` and `anomalies_zombie_drivers` are materialized as `view`, which means they cannot be registered as Trino Delta catalog entries. The `register-trino-tables.py` script explicitly skips them. Any attempt to register them will fail with a "No transaction log found" error.
- **`stg_ratings` and `stg_payments` start empty**: These models may have zero rows early in a simulation run because they only populate after trips reach `completed` state. This is expected and does not indicate a pipeline failure.
- **`fact_trips.distance_km`**: Computed inline using the Haversine formula applied to pickup/dropoff lat/lon pairs. This is not sourced from OSRM route geometry.
- **`agg_daily_driver_performance.online_minutes`**: Represents total logged-in time across all statuses (`available`, `offline`, `en_route_pickup`, `on_trip`, `driving_closer_to_home`), not only idle time. Tests enforce `en_route + on_trip <= online_minutes` against this definition.
- **Test data models**: `models/test_data/` contains DuckDB-only models (`bronze_driver_status.sql`, `bronze_gps_pings.sql`) that generate synthetic Bronze rows for local testing without a live Bronze pipeline. These should not run against the Glue target.

## Related Modules

- [services/airflow](../../services/airflow/CONTEXT.md) — Reverse dependency — Provides dbt_silver_transformation (DAG), dbt_gold_transformation (DAG), delta_maintenance (DAG) (+1 more)
- [tools](../CONTEXT.md) — Reverse dependency — Consumed by this module
- [tools/dbt/macros](macros/CONTEXT.md) — Shares DBT Transformations domain (generate_schema_name override)
- [tools/great-expectations](../great-expectations/CONTEXT.md) — Reverse dependency — Provides run_checkpoint.py, build_data_docs.py, test_connection.py
