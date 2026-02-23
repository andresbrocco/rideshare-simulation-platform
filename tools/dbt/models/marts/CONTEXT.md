# CONTEXT.md — Marts

## Purpose

The marts layer implements a star schema dimensional model for analytics on rideshare simulation data. It transforms normalized silver layer data into denormalized fact and dimension tables optimized for business intelligence queries, dashboards, and ad-hoc analysis.

## Responsibility Boundaries

- **Owns**: Star schema design, dimensional modeling, surrogate key generation, SCD Type 2 tracking for drivers and payment methods, referential integrity validation, pre-computed aggregates for dashboard performance
- **Delegates to**: Silver layer (stg_*) models for cleaned and validated source data, dbt_utils for surrogate key generation and test utilities
- **Does not handle**: Raw data ingestion (bronze layer), data validation and cleaning (silver layer), visualization (Grafana), query execution (Trino)

## Key Concepts

**Star Schema**: Fact tables (measurable events) surrounded by dimension tables (descriptive context). Facts contain foreign keys to dimensions and numeric measures. Dimensions contain descriptive attributes.

**SCD Type 2**: Slowly Changing Dimension tracking that preserves historical versions of dimension records. Each version has validity period (valid_from, valid_to) and current_flag. Enables point-in-time analysis (e.g., driver attributes at trip completion time).

**Surrogate Keys**: Generated hash-based keys used instead of natural business keys. Format: hash(natural_key + valid_from) for SCD Type 2, hash(natural_key) for non-historical dimensions. Provides stable references across dimension versions.

**Grain**: The level of detail in a fact table. Each fact table has exactly one grain (e.g., "one row per completed trip", "one row per driver status change"). Mixing grains in a single table breaks dimensional modeling rules.

## Non-Obvious Details

**SCD Type 2 Join Pattern**: Fact tables join to dimensions on surrogate key AND temporal validity. Example: `fact_trips` joins `dim_drivers` on `driver_key` where `completed_at BETWEEN valid_from AND valid_to`. This ensures facts see dimension attributes as they existed at event time.

**Conditional Dimension References**: `fact_ratings` has rater_key and ratee_key that reference different dimensions based on type (driver vs rider). Queries must join conditionally using CASE expressions or WHERE filters on rater_type/ratee_type.

**Nullable Foreign Keys**: `fact_cancellations.driver_key` is nullable because trips can be cancelled before driver matching. Referential integrity tests must account for this.

**Custom Test Macros**: Includes generic tests for business rules: `scd_validity` (no overlapping validity periods), `fee_percentage` (revenue splits sum correctly), `fare_calculation` (fare = base + surge). Located in `tests/generic/`.

**Pre-computed Aggregates**: Four aggregate tables (`agg_hourly_zone_demand`, `agg_daily_driver_performance`, `agg_daily_platform_revenue`, `agg_surge_history`) roll up facts by time and dimensions. These exist solely for dashboard query performance and duplicate data from fact tables.

**Distance Calculation Placeholder**: `fact_trips.distance_km` is always NULL. Distance calculation from coordinates is planned but not yet implemented. Duration is calculated from state timestamps.

**Materialization Strategy**: All marts use `materialized='table'` (not views or incremental). Full refresh on each dbt run. Acceptable for simulation data volumes but would need incremental strategy for production scale.

## Related Modules

- **[models/staging](../staging/CONTEXT.md)** — Silver layer models that marts reads from to build dimensional star schema
- **[models/marts/dimensions](dimensions/CONTEXT.md)** — Dimension tables (drivers, riders, zones, time, payment_methods) for star schema
- **[models/marts/facts](facts/CONTEXT.md)** — Fact tables (trips, payments, ratings, cancellations, driver_activity) capturing business events
- **[models/marts/aggregates](aggregates/CONTEXT.md)** — Pre-computed aggregates for dashboard performance
- **[tools/great-expectations](../../../../tools/great-expectations/CONTEXT.md)** — Validates Gold layer output after DBT transformation
