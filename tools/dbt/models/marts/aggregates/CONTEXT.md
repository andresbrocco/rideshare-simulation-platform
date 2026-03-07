# CONTEXT.md — Aggregates

## Purpose

Pre-aggregated analytical models that roll up Gold-layer fact and dimension data into time-bucketed KPI tables for dashboards and BI queries. Each model materializes a specific analytical domain: zone demand, driver performance, platform revenue, and surge pricing history.

## Responsibility Boundaries

- **Owns**: Time-bucketed aggregation logic, KPI derivation (idle percentage, completion rate, avg fare), and revenue split computation
- **Delegates to**: `fact_trips`, `fact_payments`, `fact_ratings`, `fact_driver_activity`, `fact_cancellations`, `dim_zones`, `dim_drivers`, `dim_time` for source data; `stg_surge_updates` for raw surge events
- **Does not handle**: Deduplication, schema validation, or SCD management (those belong to Silver/Gold fact/dimension layers)

## Key Concepts

- **`online_minutes`**: In `agg_daily_driver_performance`, this is the sum of all `fact_driver_activity` duration across every active status (available, en_route_pickup, on_trip, etc.) — it is total logged-in time, not idle-only time. This satisfies the test `en_route_minutes + on_trip_minutes <= online_minutes`.
- **`idle_pct`**: Derived as `(online_minutes - en_route_minutes - on_trip_minutes) / online_minutes * 100`. Represents the fraction of online time the driver was neither en route nor on a trip.
- **Completion rate alignment**: `agg_hourly_zone_demand` buckets completed trips by `requested_at` (not `completed_at`) so that completions always fall in the same hour bucket as their originating request. This guarantees `completed_trips <= requested_trips` for any given zone/hour, which is enforced by a dbt test.
- **Revenue split integrity**: `agg_daily_platform_revenue` enforces `abs(platform_fees + driver_payouts - total_revenue) < 0.01` via a dbt expression test to catch floating-point drift in the fee split.

## Non-Obvious Details

- `agg_hourly_zone_demand` uses a `FULL OUTER JOIN` between `hourly_requests` and `hourly_completions` to preserve zone/hour combinations that have requests but no completions (and vice versa). The `coalesce(..., 1.0)` default for `avg_surge_multiplier` means hours with no completions report a neutral multiplier rather than null.
- `agg_surge_history` aggregates from `stg_surge_updates` (a staging model, not a fact table) — it is the one aggregate that bypasses the fact layer entirely and reads directly from Silver staging.
- `agg_daily_platform_revenue` uses an `INNER JOIN` to `fact_payments`, so trips without a payment record are excluded. This is intentional to avoid counting unpaid trips in revenue figures.
- All models are materialized as `table` (not `view`) to support Trino Delta Lake registration.

## Related Modules

- [tools/dbt/models/marts/dimensions](../dimensions/CONTEXT.md) — Dependency — Gold-layer dimension tables forming the dimension side of the star schema, with ...
- [tools/dbt/models/marts/facts](../facts/CONTEXT.md) — Dependency — Gold-layer fact tables for the rideshare star schema covering completed trips, p...
- [tools/dbt/models/staging](../../staging/CONTEXT.md) — Dependency — Silver layer JSON parsing, deduplication, validation filtering, and anomaly dete...
- [tools/dbt/tests/singular](../../../tests/singular/CONTEXT.md) — Reverse dependency — Consumed by this module
