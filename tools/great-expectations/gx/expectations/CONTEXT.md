# CONTEXT.md — Expectations

## Purpose

Stores Great Expectations expectation suite definitions (JSON) that validate data quality at the Silver and Gold layers of the medallion lakehouse. Each JSON file maps to one DBT model and is executed by Airflow after DBT transformations complete.

## Responsibility Boundaries

- **Owns**: Column-level data quality rules for Silver staging tables and Gold star schema tables
- **Delegates to**: Great Expectations runtime (checkpoint execution), Airflow (orchestration), DBT (producing the data being validated)
- **Does not handle**: Bronze layer validation, schema enforcement (handled by Schema Registry upstream), or row-count thresholds

## Key Concepts

**Expectation suite**: A named JSON file containing an array of expectation objects, each with an `expectation_type` and `kwargs`. The suite name must match the target asset name used in checkpoint configuration.

**`mostly` threshold**: GX-specific parameter (0.0–1.0) allowing a percentage of rows to violate a rule before the suite fails. Used deliberately on geospatial bounds and fare/distance ranges to tolerate simulation edge cases without failing the pipeline entirely. Absent `mostly` means 100% enforcement.

**Directory layout mirrors medallion layers**:
- `silver/` — one suite per staging model (`silver_stg_*`), validating event-level fields (unique `event_id`, non-null timestamps, enum-constrained state fields, Sao Paulo bounding-box lat/lon)
- `gold/dimensions/` — surrogate key uniqueness, SCD Type 2 field completeness (`valid_from`, `valid_to`, `current_flag`)
- `gold/facts/` — foreign key non-nullness (`driver_key`, `rider_key`, `trip_key`), domain value sets, numeric range bounds
- `gold/aggregates/` — aggregate metric plausibility bounds (e.g., `trips_completed` 0–500, `total_duration_minutes` 0–1440)

## Non-Obvious Details

- Silver suites validate event-sourced records and enforce `event_id` uniqueness to catch Bronze deduplication failures propagating to Silver.
- Gold dimension suites validate SCD Type 2 structure by asserting `valid_from`, `valid_to`, and `current_flag` are non-null on every row; they do not assert that exactly one current row exists per natural key (that constraint lives in DBT tests).
- Geospatial bounds (`latitude` -23.8 to -23.3, `longitude` -46.9 to -46.3) encode the Sao Paulo metro simulation area. The `mostly: 0.99` tolerance accommodates rare GPS outlier events that pass Bronze but are flagged as anomalies in Silver rather than dropped.
- Trip state enum values differ between Silver (`snake_case`, e.g. `"offer_sent"`) and Gold (`UPPER_CASE`, e.g. `"OFFER_REJECTED"`), reflecting DBT normalization in the Silver-to-Gold transformation.
- The `gold/` subdirectories contain `.gitkeep` files alongside JSON suites; new Gold models require a corresponding JSON file added here to be included in Airflow validation checkpoints.

## Related Modules

- [tools/great-expectations](../../CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite)
- [tools/great-expectations/gx/expectations/gold](gold/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2 validation)
- [tools/great-expectations/gx/expectations/gold](gold/CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite, mostly threshold)
- [tools/great-expectations/gx/expectations/gold/dimensions](gold/dimensions/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/silver](silver/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
