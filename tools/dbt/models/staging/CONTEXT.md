# CONTEXT.md — Staging

## Purpose

Provides the Silver layer of the medallion architecture. Parses raw Kafka JSON payloads stored in the Bronze Delta tables into typed, deduplicated, schema-validated relations. Also hosts anomaly detection logic that identifies data quality issues (GPS outliers, impossible speeds, zombie drivers) and surfaces them through a unified anomaly catalog.

## Responsibility Boundaries

- **Owns**: JSON parsing from `_raw_value`, type casting, deduplication by `event_id`, field-level validation filtering, and anomaly detection queries
- **Delegates to**: `tools/dbt/macros/` for all cross-adapter SQL (JSON extraction, timestamp conversion, source resolution, epoch arithmetic)
- **Does not handle**: Business aggregation, dimension modeling, SCD Type 2 history tracking, or Gold-layer star schema construction — those belong to `models/marts/`

## Key Concepts

**Two-tier deduplication for profile models.** `stg_drivers` and `stg_riders` use two sequential `row_number()` window functions: first deduplication by `event_id` (at-least-once Kafka delivery), then a second pass by `(driver_id/rider_id, timestamp)` to eliminate any duplicate profile events for the same entity at the same moment before they propagate to SCD Type 2 dimension tables downstream.

**Anomaly sub-models vs. `anomalies_all`.** Three anomaly detection views (`anomalies_gps_outliers`, `anomalies_zombie_drivers`, `anomalies_impossible_speeds`) are individual detectors. `anomalies_all` is a materialized table that unions all three into a single catalog with a normalized `(anomaly_type, entity_type, entity_id, detected_at, anomaly_details)` schema. The `anomaly_details` column is a manually constructed JSON string rather than a native struct, for cross-adapter compatibility.

**Zombie driver detection.** A driver is flagged as a zombie if their current status is active (`available`, `en_route_pickup`, `on_trip`, `driving_closer_to_home`) but no GPS ping has arrived within the last 10 minutes. The calculation uses `epoch_seconds()` macro and a left join with `latest_gps_per_driver`, falling back to `last_status_timestamp` when no GPS history exists for a driver.

**Geospatial bounding box.** All GPS models hard-code the Sao Paulo metro area bounding box: latitude `[-23.8, -23.3]`, longitude `[-46.9, -46.3]`. Points outside this range are filtered out in `stg_gps_pings` and collected as `anomalies_gps_outliers`. This means `anomalies_gps_outliers` will always be empty in practice because `stg_gps_pings` already excludes outliers — the anomaly model reads from the staging model, not directly from Bronze.

**Incremental watermark pattern.** All `stg_*` models use `_ingested_at > max(_ingested_at)` as the incremental filter, falling back to epoch zero (`1970-01-01`) via `to_ts()` macro on first run. This is a processing-time watermark, not an event-time watermark, so late-arriving Bronze records within a batch will be caught on the next run.

**`trip_state` derivation.** In `stg_trips`, `trip_state` is derived from `event_type` by splitting on `.` and taking the third segment (index 2), lowercased. Raw event types follow the pattern `trip.state.<state_name>`. This parsing is fragile to event type naming changes upstream.

## Non-Obvious Details

- `anomalies_gps_outliers` and `anomalies_zombie_drivers` are materialized as views, not Delta tables. The `register-trino-tables.py` script skips registering views in the Hive Metastore because Trino cannot register a view as a Delta table. Query these anomaly sub-models through dbt or directly via DuckDB only.
- `stg_payments` does not perform deduplication by `event_id` window function — it filters on positive monetary amounts (`fare_amount > 0`, `platform_fee_amount > 0`, `driver_payout_amount > 0`) and relies on the incremental merge `unique_key='event_id'` for deduplication rather than an explicit CTE. This is inconsistent with `stg_trips` and `stg_gps_pings`.
- `stg_gps_pings` constructs a `location` array column using an inline adapter branch (`list_value` for DuckDB, `array` for Spark/Glue) rather than a macro, making it the only place in staging with a raw `target.type` check in SQL.
- `stg_ratings` and `stg_payments` may return zero rows early in a simulation run because trips must complete before ratings and payments are emitted. This is expected and not an error.
- The `sources.yml` `delta_source()` macro handles two fundamentally different access patterns: DuckDB uses direct S3 path scans (`delta_scan('s3://...')`), while Spark/Glue uses Hive Metastore catalog references. The staging SQL itself is adapter-agnostic because all source access is behind this macro.

## Related Modules

- [tools/dbt/macros/cross_db](../../macros/cross_db/CONTEXT.md) — Dependency — SQL dialect abstraction layer for DuckDB (local) and Spark/Glue (production) dif...
- [tools/dbt/models/marts](../marts/CONTEXT.md) — Reverse dependency — Provides dim_drivers, dim_riders, dim_zones (+12 more)
- [tools/dbt/models/marts/aggregates](../marts/aggregates/CONTEXT.md) — Reverse dependency — Provides agg_hourly_zone_demand, agg_daily_driver_performance, agg_daily_platform_revenue (+1 more)
- [tools/dbt/models/marts/facts](../marts/facts/CONTEXT.md) — Reverse dependency — Provides fact_trips, fact_payments, fact_ratings (+3 more)
- [tools/dbt/tests](../../tests/CONTEXT.md) — Reverse dependency — Provides test_dim_drivers_scd_type2, test_dim_payment_methods_scd_type2, test_dim_riders_current_state (+8 more)
- [tools/great-expectations/gx/expectations/silver](../../../great-expectations/gx/expectations/silver/CONTEXT.md) — Reverse dependency — Provides silver_stg_drivers, silver_stg_riders, silver_stg_trips (+5 more)
