# CONTEXT.md — Staging

## Purpose

The staging layer transforms raw Bronze events into clean, validated datasets ready for dimensional modeling. This layer acts as the data quality gateway, ensuring only valid data flows downstream to the Gold layer.

## Responsibility Boundaries

- **Owns**: JSON parsing from Bronze `_raw_value` columns, deduplication on `event_id`, coordinate and enum validation, timestamp standardization to UTC, anomaly detection for data quality monitoring
- **Delegates to**: Gold layer for dimensional modeling (SCD Type 2, surrogate keys, star schema), Great Expectations for pipeline validation, Airflow for orchestration
- **Does not handle**: Business aggregations, surrogate key generation, or denormalized views (those belong in Gold layer)

## Key Concepts

**Incremental Materialization**: All staging models use DBT's incremental strategy with merge on `event_id` to handle Kafka's at-least-once delivery. Watermark on `_ingested_at` ensures only new data is processed after initial full refresh.

**Deduplication Strategy**: Row-number window functions (`row_number() over (partition by event_id order by _ingested_at desc)`) keep the latest version of duplicate events.

**Anomaly Detection Models**: Specialized models (`anomalies_gps_outliers`, `anomalies_impossible_speeds`, `anomalies_zombie_drivers`) flag data quality issues. Consolidated in `anomalies_all` for monitoring dashboards.

**Delta Source Pattern**: Custom macro `delta_source('bronze', 'bronze_trips')` reads from Bronze layer Delta tables stored in MinIO.

## Non-Obvious Details

**Event State Parsing**: Trip state is extracted from event_type using `split(event_type, '\\.')[1]` because Bronze stores `trip.requested` while staging needs `requested`.

**Coordinate Extraction**: GPS coordinates stored as JSON arrays `[lat, lon]` are extracted using `get_json_object(_raw_value, '$.pickup_location[0]')` for latitude and `[1]` for longitude.

**SCD Type 2 Preparation**: Driver profiles (`stg_drivers`) preserve all create/update events to enable SCD Type 2 tracking in Gold layer. Rider profiles (`stg_riders`) do not use SCD Type 2 and only track current state.

**Platform Fee Calculation**: Payment models validate that `platform_fee_amount + driver_payout_amount = fare_amount` through filtering (`where fare_amount > 0 and platform_fee_amount > 0 and driver_payout_amount > 0`).

**Sao Paulo Bounds**: GPS coordinate validation uses hardcoded bounds (latitude: -23.8 to -23.3, longitude: -46.9 to -46.3) specific to the simulation geography.

## Related Modules

- **[tools/dbt/macros](../../macros/CONTEXT.md)** — Provides delta_source and source_with_empty_guard macros used by all staging models
- **[services/bronze-ingestion](../../../../services/bronze-ingestion/CONTEXT.md)** — Data source; staging reads from Bronze Delta tables created by the Python ingestion consumer
