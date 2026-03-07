# CONTEXT.md — Gold Expectations

## Purpose

Great Expectations suites that validate the Gold layer (star schema) of the medallion lakehouse. Each JSON file corresponds to one Gold table and defines the quality contract that must pass before data is considered fit for analytics consumption via Trino.

## Responsibility Boundaries

- **Owns**: Schema contracts (not-null, uniqueness, value sets, numeric ranges) for all Gold tables
- **Delegates to**: Great Expectations runtime for execution; Airflow DAGs for orchestration timing
- **Does not handle**: Silver-layer validation (handled in `gx/expectations/silver/`), cross-table referential integrity, or business logic correctness

## Key Concepts

Suites are organized into three sub-groups mirroring the Gold schema topology:

- **dimensions/**: SCD Type 2 dimension tables (`dim_drivers`, `dim_riders`, `dim_zones`, `dim_time`, `dim_payment_methods`). Surrogate key (`*_key`) uniqueness and not-null are enforced on every dimension.
- **facts/**: Fact tables (`fact_trips`, `fact_payments`, `fact_ratings`, `fact_cancellations`, `fact_driver_activity`). All foreign key columns (`driver_key`, `rider_key`, etc.) are required not-null; numeric measures have bounded ranges.
- **aggregates/**: Pre-aggregated mart tables (`agg_daily_driver_performance`, `agg_hourly_zone_demand`). Bounded ranges reflect realistic simulation output volumes rather than strict business rules.

## Non-Obvious Details

- **`mostly` thresholds instead of strict 100%**: Several expectations (e.g., `license_plate` regex at 0.95, `distance_km` bounds at 0.99) use `mostly` rather than strict enforcement. This is intentional — simulation-generated data can occasionally produce edge-case values that would fail a 100% check but do not indicate pipeline failure.
- **SCD Type 2 fields validated at Gold only**: `valid_from`, `valid_to`, and `current_flag` are only checked in `gold_dim_drivers` and `gold_dim_riders`. There is no equivalent in Silver, which stores the raw history without SCD semantics.
- **`gold_fact_driver_activity` status set is a subset of simulation states**: The allowed values `["online", "offline", "on_trip", "available"]` are coarser than the simulation's internal state machine. Silver-to-Gold transformation maps finer-grained simulation statuses into these four categories before the expectation runs.
- **`avg_surge_multiplier` minimum is 1.0**: This enforces that surge is never below baseline (1x), which would indicate a data error rather than a valid business scenario.
- **`completion_rate` bounded 0–1**: This is a ratio, not a percentage — the suite enforces float range, not integer percent, which differs from `idle_pct` in `agg_daily_driver_performance` which is bounded 0–100.
- **`.gitkeep` files in subdirectories**: `facts/` and `dimensions/` contain `.gitkeep` files alongside JSON suites, indicating these directories were pre-created before all suites were populated.

## Related Modules

- [tools/dbt/models/marts](../../../../dbt/models/marts/CONTEXT.md) — Dependency — Gold layer star schema dimensional model for analytics on rideshare trip, paymen...
- [tools/great-expectations](../../../CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite)
- [tools/great-expectations/gx/expectations](../CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2 validation)
- [tools/great-expectations/gx/expectations](../CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite, mostly threshold)
- [tools/great-expectations/gx/expectations/gold/dimensions](dimensions/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/silver](../silver/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
