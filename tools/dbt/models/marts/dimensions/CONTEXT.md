# CONTEXT.md — Dimensions

## Purpose

Gold-layer dimension tables forming the "dimension" side of the star schema. These models produce surrogate-keyed, analytics-ready reference tables consumed by fact models in joins.

## Responsibility Boundaries

- **Owns**: Surrogate key generation, SCD Type 2 validity windows, current-record flagging, date spine construction
- **Delegates to**: `stg_drivers`, `stg_riders` (Silver staging for entity history); `zones` seed (static geographic reference); `dbt_utils` and cross-DB macros for key generation and date functions
- **Does not handle**: Fact metrics, event counts, or trip-level data

## Key Concepts

**SCD Type 2 (Slowly Changing Dimension)** — `dim_drivers` and `dim_payment_methods` use SCD2: each change in a driver's profile or a rider's payment method produces a new row with `valid_from`/`valid_to` timestamps and a `current_flag`. Surrogate keys are composite (`driver_id + valid_from`, `payment_method_key + valid_from`) so each historical record is uniquely addressable. The sentinel value `9999-12-31 23:59:59` marks open-ended (current) records.

**Current-snapshot dimension** — `dim_riders` departs from SCD2: it keeps only the most recent row per `rider_id` using `row_number() ... order by timestamp desc`. The surrogate key is keyed on `rider_id` alone, giving one row per rider.

**dim_payment_methods partition key choice** — The `lead()` window partitions by `(rider_id, payment_method_type)` only, not by masked card number. This is intentional: partitioning by masked number would produce independent SCD chains per card, leading to multiple `current_flag = true` rows per `(rider_id, payment_method_type)` and duplicate joins in `fact_payments`. The inline comment in the SQL explains this explicitly.

**dim_zones source** — Built directly from the `zones` dbt seed (static CSV), not from a staging model. Geographic attributes (`demand_multiplier`, `surge_sensitivity`, `subprefecture`) come from simulation configuration, not from event data. Coordinate bounds are validated to the Sao Paulo region (lat −25 to −23, lon −47 to −46).

**dim_time** — Generated via `dbt_utils.date_spine` from 2024-01-01 through 2026-12-31. Day-of-week conversion normalizes the DB-native representation (which varies by engine) to ISO 8601 (1=Monday, 7=Sunday) using cross-DB macros (`day_of_week`, `format_date`).

## Non-Obvious Details

- `dim_drivers` has an `scd_validity` custom generic test (defined in `tools/dbt/tests/generic/`) that validates non-overlapping, contiguous validity windows. `dim_payment_methods` applies the same test, referencing `payment_method_id` as its "driver_id column" argument.
- `dim_riders` does not use SCD2 despite the source having timestamped rows. Rider profile changes are treated as corrections, not history to preserve — only the latest record matters for analytics.
- `dim_payment_methods` produces a two-level surrogate: `payment_method_id` identifies a unique `(rider_id, type, masked_number)` combination; `payment_method_key` further disambiguates across validity periods for the same payment slot.
- The date spine hard-codes a three-year range. Queries for dates outside 2024–2026 will find no matching `dim_time` row.

## Related Modules

- [tools/dbt/macros/cross_db](../../../macros/cross_db/CONTEXT.md) — Dependency — SQL dialect abstraction layer for DuckDB (local) and Spark/Glue (production) dif...
- [tools/dbt/models/marts](../CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
- [tools/dbt/models/marts/aggregates](../aggregates/CONTEXT.md) — Reverse dependency — Provides agg_hourly_zone_demand, agg_daily_driver_performance, agg_daily_platform_revenue (+1 more)
- [tools/dbt/models/marts/facts](../facts/CONTEXT.md) — Reverse dependency — Provides fact_trips, fact_payments, fact_ratings (+3 more)
- [tools/dbt/tests](../../../tests/CONTEXT.md) — Reverse dependency — Provides test_dim_drivers_scd_type2, test_dim_payment_methods_scd_type2, test_dim_riders_current_state (+8 more)
- [tools/great-expectations/gx/expectations/gold/dimensions](../../../../great-expectations/gx/expectations/gold/dimensions/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
- [tools/great-expectations/gx/expectations/gold/dimensions](../../../../great-expectations/gx/expectations/gold/dimensions/CONTEXT.md) — Shares Star Schema and Data Modeling domain (surrogate key)
