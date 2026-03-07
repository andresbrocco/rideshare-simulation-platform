# CONTEXT.md — Facts

## Purpose

Gold-layer fact tables for the rideshare star schema. Each table models a distinct business event type: completed trips, payments, ratings, cancellations, driver status periods, and offer attempts. All fact tables are materialized as Delta tables and join against SCD Type 2 dimensions using temporal validity windows.

## Responsibility Boundaries

- **Owns**: Final fact rows for the Gold layer; surrogate key generation; derived metrics (distance, duration, platform fee split, response latency); `cancellation_stage` enrichment
- **Delegates to**: `stg_*` staging models for parsing and Silver-layer deduplication; dimension tables for surrogate key lookups; the `epoch_seconds` macro for cross-DB timestamp arithmetic
- **Does not handle**: Raw event parsing, deduplication of source events (Silver responsibility), or aggregate rollups (those live in `marts/aggregates`)

## Key Concepts

- **SCD Type 2 temporal join**: `dim_drivers` and `dim_payment_methods` carry `valid_from`/`valid_to` columns. Fact tables join on `entity_id AND event_timestamp >= valid_from AND event_timestamp < valid_to` to resolve the correct dimension record at the time the event occurred.
- **offer_sequence**: `fact_offers` is grain-per-offer-attempt (`trip_id` + `offer_sequence`). A single trip may produce multiple offer rows if earlier offers are rejected or expire. This enables funnel analysis across the offer lifecycle.
- **cancellation_stage**: Derived field in `fact_cancellations` identifying the last non-cancelled state before a trip was cancelled (e.g., `requested`, `driver_assigned`, `in_transit`). Computed by ranking all prior trip events descending by timestamp and taking rank 1.
- **Polymorphic rating join**: `fact_ratings` rater/ratee can be either a driver or a rider. The model uses conditional `CASE` expressions to resolve `rater_key` and `ratee_key` from whichever dimension table applies.

## Non-Obvious Details

- `fact_trips` contains **only completed trips**. Cancelled trips are a separate fact (`fact_cancellations`). Both pivot `stg_trips` events using `pivot by trip_state`, so the split is logical, not a source-level filter that would drop data.
- `distance_km` in `fact_trips` is computed inline via the Haversine formula from raw lat/lon coordinates. It is not sourced from OSRM or the simulation engine. The Silver layer does not pre-compute this value.
- `fact_payments` hardcodes a 25% platform fee. `platform_fee = round(total_fare * 0.25, 2)` and `driver_payout = total_fare - platform_fee` (not `total_fare * 0.75`) to guarantee the two fields sum exactly to `total_fare` without floating-point drift. This is enforced by the `fee_percentage` generic test in `schema.yml`.
- `fact_payments` uses a secondary `_dedup_rn` window (latest `valid_from`) to handle edge cases where `dim_payment_methods` has overlapping SCD records for the same rider + method + timestamp.
- `fact_driver_activity` excludes the final open-ended status period (`WHERE status_end IS NOT NULL`) because duration cannot be computed without a closing timestamp. This means the most recent status for any driver is always absent from this table until superseded.
- `fact_offers` uses a `LEFT JOIN` from `sent` to `resolved` — unresolved offers land as `outcome = 'pending'`. Schema tests enforce `outcome IN ('accepted', 'rejected', 'expired', 'pending')`.
- `duration_minutes` and `response_seconds` use the `epoch_seconds` Jinja macro (defined in `tools/dbt/macros/cross_db/`) rather than a direct `DATEDIFF`, enabling the same SQL to run on both Trino (Delta Lake) and DuckDB.

## Related Modules

- [services/simulation/src/geo](../../../../../services/simulation/src/geo/CONTEXT.md) — Shares Geospatial Processing domain (haversine distance)
- [tools/dbt/macros/cross_db](../../../macros/cross_db/CONTEXT.md) — Dependency — SQL dialect abstraction layer for DuckDB (local) and Spark/Glue (production) dif...
- [tools/dbt/models/marts/aggregates](../aggregates/CONTEXT.md) — Reverse dependency — Provides agg_hourly_zone_demand, agg_daily_driver_performance, agg_daily_platform_revenue (+1 more)
- [tools/dbt/models/marts/dimensions](../dimensions/CONTEXT.md) — Dependency — Gold-layer dimension tables forming the dimension side of the star schema, with ...
- [tools/dbt/models/staging](../../staging/CONTEXT.md) — Dependency — Silver layer JSON parsing, deduplication, validation filtering, and anomaly dete...
- [tools/dbt/tests](../../../tests/CONTEXT.md) — Reverse dependency — Provides test_dim_drivers_scd_type2, test_dim_payment_methods_scd_type2, test_dim_riders_current_state (+8 more)
- [tools/dbt/tests/singular](../../../tests/singular/CONTEXT.md) — Reverse dependency — Consumed by this module
