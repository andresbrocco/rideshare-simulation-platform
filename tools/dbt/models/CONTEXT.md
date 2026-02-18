# CONTEXT.md — DBT Models

## Purpose

Transforms raw Kafka events from Bronze layer into a dimensional data warehouse following medallion architecture. Implements incremental ETL with data quality validation, SCD Type 2 tracking, and anomaly detection for rideshare analytics.

## Responsibility Boundaries

- **Owns**: SQL transformation logic, incremental merge strategies, SCD Type 2 implementation, data quality tests, anomaly detection models
- **Delegates to**: Bronze ingestion service for raw Kafka-to-Delta persistence, Great Expectations for post-transformation validation, analytics tools (Grafana) for visualization
- **Does not handle**: Real-time streaming transformations, API serving, schema evolution in Bronze layer

## Key Concepts

**Medallion Architecture**: Three-tier data refinement pattern
- Bronze: Raw JSON from Kafka stored in Delta format with Kafka metadata
- Silver (staging/): Parsed, deduplicated, validated events with business logic applied
- Gold (marts/): Star schema with dimensions, facts, and aggregates for analytics

**SCD Type 2**: Slowly Changing Dimensions track historical changes via temporal validity windows. `dim_drivers` and `dim_payment_methods` use `valid_from`/`valid_to` columns with `current_flag` to capture profile changes over time. Fact tables join on temporal validity to get correct historical context.

**Incremental Merge**: Staging models use `incremental_strategy='merge'` with `unique_key` on `event_id` to handle late-arriving duplicates. Watermark on `_ingested_at` ensures only new data is processed in subsequent runs.

**Delta Source Pattern**: Custom `delta_source()` macro reads directly from S3 paths (`s3a://rideshare-bronze/`) using Delta format syntax. `source_with_empty_guard()` macro handles empty Delta tables gracefully by unioning typed NULL columns.

## Non-Obvious Details

**Deduplication Strategy**: Bronze layer may contain duplicate events due to Kafka retries. Staging models deduplicate on `event_id` keeping the record with latest `_ingested_at` timestamp using `row_number()` window function.

**Trip State Parsing**: Trip events have `event_type` like "trip.matched" but models extract lowercase state "matched" using `split()` and `try_element_at()` for backward compatibility with schema changes.

**Temporal Joins**: `fact_trips` joins `dim_drivers` with temporal predicate `ct.completed_at >= dr.valid_from and ct.completed_at < dr.valid_to` to capture which vehicle the driver used at trip completion time.

**Anomaly Detection**: Separate view models (`anomalies_*`) flag data quality issues without blocking pipeline execution. Examples include impossible speeds (>200 km/h calculated via Haversine formula), GPS outliers beyond Sao Paulo bounds, and zombie drivers (active status with no GPS pings).

**Empty Table Handling**: Profile dimension sources may be empty at first run. `source_with_empty_guard()` macro unions real data with typed NULL columns filtered by `where 1=0` to ensure consistent schema even when Delta tables are empty.
