# CONTEXT.md — Marts

## Purpose

The Gold layer of the medallion lakehouse. Transforms Silver staging models into a star schema dimensional model that powers Grafana dashboards, Trino ad-hoc queries, and business analytics. All tables are materialized as Delta tables registered in Trino.

## Responsibility Boundaries

- **Owns**: Star schema design, surrogate key generation, SCD Type 2 validity periods, business metric computation, referential integrity enforcement
- **Delegates to**: `models/staging` for cleaned Silver source data; `macros/cross_db` for cross-engine SQL compatibility (e.g., `epoch_seconds`)
- **Does not handle**: Raw ingestion, deduplication, parsing (those are Bronze/Silver concerns)

## Key Concepts

**Star Schema Layout**: Three sub-directories map to the three table types:
- `dimensions/` — `dim_drivers` (SCD Type 2), `dim_riders` (current state), `dim_zones` (static), `dim_time` (calendar), `dim_payment_methods` (SCD Type 2)
- `facts/` — `fact_trips`, `fact_payments`, `fact_ratings`, `fact_cancellations`, `fact_offers`, `fact_driver_activity`
- `aggregates/` — pre-computed rollups for dashboard performance (`agg_hourly_zone_demand`, `agg_daily_driver_performance`, `agg_daily_platform_revenue`, `agg_surge_history`)

**SCD Type 2 (dim_drivers, dim_payment_methods)**: Each row represents one version of an entity. `valid_from`/`valid_to` bound the window; `valid_to` is `9999-12-31` for the current record; `current_flag = true` identifies current rows. Surrogate key is hashed from `(natural_key, valid_from)` so each version gets a distinct key.

**Temporal fact joins**: Facts always join to `dim_drivers` on both the natural key and a time-range condition (`fact_timestamp BETWEEN valid_from AND valid_to`), capturing the driver profile as it existed at event time — not the current profile.

**Bidirectional ratings (fact_ratings)**: `rater_key` and `ratee_key` each polymorphically reference either `dim_drivers` or `dim_riders` depending on `rater_type`/`ratee_type`. Queries must apply `WHERE rater_type = 'driver'` (or rider) before joining to the appropriate dimension table.

**Offer state machine pivoting (fact_offers)**: Offers are reconstructed from raw trip state events. Each offer cycle is identified by `(trip_id, offer_sequence)`. The model pivots `offer_sent` events against `driver_assigned`/`offer_rejected`/`offer_expired` resolution events to produce one row per offer attempt with computed `outcome` and `response_seconds`.

## Non-Obvious Details

- `fact_trips.distance_km` is computed via an inline Haversine formula from pickup/dropoff lat/lon coordinates. A null result means coordinates were missing upstream, not a model bug.
- `fact_trips` reconstructs timestamps by pivoting multiple state rows from `stg_trips` (one row per `trip_state`). It takes only `rn = 1` per `(trip_id, trip_state)` to de-duplicate events that were recorded more than once.
- `agg_daily_driver_performance.online_minutes` counts all logged-in time across all statuses (available, offline, en_route_pickup, on_trip). It is not limited to idle/online time. The test `en_route_minutes + on_trip_minutes <= online_minutes` depends on this inclusive definition.
- `fact_payments` is validated by custom `fee_percentage` tests asserting `platform_fee = 25%` and `driver_payout = 75%` of `total_fare`.
- `fact_cancellations.driver_key` is nullable: trips cancelled before a driver was assigned have no driver dimension record.
- `marts_overview.md` is a dbt doc block used with `{{ doc('...') }}` references in schema descriptions, not a standalone documentation file.

## Related Modules

- [tools/dbt/macros/cross_db](../../macros/cross_db/CONTEXT.md) — Dependency — SQL dialect abstraction layer for DuckDB (local) and Spark/Glue (production) dif...
- [tools/dbt/models/marts/dimensions](dimensions/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
- [tools/dbt/models/staging](../staging/CONTEXT.md) — Dependency — Silver layer JSON parsing, deduplication, validation filtering, and anomaly dete...
- [tools/great-expectations/gx/expectations/gold](../../../great-expectations/gx/expectations/gold/CONTEXT.md) — Reverse dependency — Provides gold_dim_drivers, gold_dim_riders, gold_dim_zones (+9 more)
- [tools/great-expectations/gx/expectations/gold/dimensions](../../../great-expectations/gx/expectations/gold/dimensions/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
