# CONTEXT.md — DBT

## Purpose

Implements the Silver and Gold layers of a medallion lakehouse architecture (Bronze → Silver → Gold) for ride-sharing analytics. Transforms raw Kafka events stored in Bronze Delta tables into a dimensional model with staging tables, dimensions, facts, and aggregates.

## Responsibility Boundaries

- **Owns**: Data transformation logic (Bronze to Silver to Gold), data quality tests, incremental processing strategy, SCD Type 2 implementation, anomaly detection
- **Delegates to**: Databricks Structured Streaming (Bronze layer ingestion from Kafka), Spark Thrift Server (query execution), Airflow/MWAA (orchestration scheduling), Great Expectations (additional data validation)
- **Does not handle**: Raw event ingestion from Kafka, infrastructure provisioning, stream processing, or real-time serving

## Key Concepts

### Medallion Architecture Layers

- **Bronze**: Raw Kafka events in Delta format with `_raw_value` JSON column (managed externally by Databricks Structured Streaming)
- **Silver** (`staging/`): Cleaned, parsed, deduplicated events using incremental materialization with merge strategy
- **Gold** (`marts/`): Business-ready dimensional model (star schema) with surrogate keys

### Empty Source Guard

Custom macro `source_with_empty_guard` that prevents failures when Bronze Delta tables exist but have no data or schema. Required because Spark raises `DELTA_READ_TABLE_WITHOUT_COLUMNS` exception on empty tables. All staging models must use this pattern when reading from Bronze.

### SCD Type 2

Tracks historical changes to driver profiles (`dim_drivers`) and payment methods (`dim_payment_methods`) using `valid_from`, `valid_to`, and `current_flag` columns. Custom test `test_scd_validity` validates non-overlapping validity windows.

### Incremental Processing

Staging models use `incremental_strategy: merge` with `_ingested_at` watermark to process only new data. Facts and aggregates use full refresh on each run.

## Non-Obvious Details

- **JSON Parsing**: Bronze layer stores entire Kafka message as JSON string in `_raw_value`. Staging models parse using `get_json_object()` for each field.
- **Trip State Extraction**: Trip events arrive as `trip.requested`, `trip.matched`, etc. but staging model extracts just the state portion (`requested`, `matched`) using `split()` and `try_element_at()`.
- **Test Data Scripts**: Helper Python scripts in root directory seed Bronze tables via PyHive for local development. These are for testing DBT transformations, not production data pipelines.
- **Schema Evolution**: `on_schema_change: fail` for staging layer ensures explicit handling of upstream schema changes rather than silent failures.
- **File Format**: All models explicitly use `file_format='delta'` for ACID transaction support and time travel capabilities.

## Related Modules

- **[services/spark-streaming](../spark-streaming/CONTEXT.md)** — Data source; DBT reads from Bronze Delta tables created by streaming jobs
- **[services/airflow](../airflow/CONTEXT.md)** — Orchestration partner; Airflow schedules DBT runs and triggers data validation
- **[quality/great-expectations](../../quality/great-expectations/CONTEXT.md)** — Validation partner; Great Expectations validates DBT output for data quality
- **[analytics/superset](../../analytics/superset/CONTEXT.md)** — Data consumer; Superset dashboards query Gold dimensional models created by DBT
- **[schemas/lakehouse](../../schemas/lakehouse/CONTEXT.md)** — Bronze schema reference; DBT staging models parse `_raw_value` using structure defined in lakehouse schemas
