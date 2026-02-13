# CONTEXT.md — Facts

## Purpose

Fact tables in the star schema that capture measurable business events from the rideshare simulation. Each fact represents a grain of transaction data (completed trips, payments, ratings, cancellations, driver activity periods) with foreign keys to dimensions and numeric measures for analysis.

## Responsibility Boundaries

- **Owns**: Fact table grain definition, surrogate key generation for facts, temporal joins to SCD Type 2 dimensions, measure calculations (duration, platform fees, driver payouts), deduplication of duplicate events via row_number()
- **Delegates to**: Silver layer (stg_*) models for cleaned source events, dimension models for descriptive attributes, dbt_utils for surrogate key hashing, custom macros for epoch conversions
- **Does not handle**: Raw event parsing (silver layer), dimension attribute management (dimensions layer), aggregation for dashboards (aggregates layer), schema design changes

## Key Concepts

**Fact Grain**: Each fact table has exactly one grain that defines what one row represents. Mixing grains breaks dimensional modeling rules. Grains in this layer: one row per completed trip, one row per payment, one row per rating, one row per cancellation, one row per driver status period.

**Temporal Joins to SCD Type 2**: Fact tables join dimensions on both surrogate key AND temporal validity period. Pattern: `fact.event_timestamp >= dim.valid_from AND fact.event_timestamp < dim.valid_to`. This ensures facts reference dimension attributes as they existed at event time.

**Row Number Deduplication**: Source events may arrive multiple times for same state. CTEs use `row_number() over (partition by trip_id, trip_state order by timestamp)` to deduplicate and take first occurrence.

**Conditional Dimension References**: `fact_ratings` uses rater_key/ratee_key that can reference either drivers or riders based on rater_type/ratee_type. Queries must conditionally join using CASE or WHERE filters.

## Non-Obvious Details

**Distance Always NULL**: `fact_trips.distance_km` is always NULL. Distance calculation from lat/lon coordinates is planned but not implemented. Duration is calculated from state timestamps using custom `epoch_seconds()` macro.

**Platform Fee Split**: `fact_payments` hardcodes 25% platform fee and 75% driver payout. Driver payout is derived as `total_fare - round(total_fare * 0.25, 2)` to ensure exact sum without floating point errors. Custom test `fee_percentage` validates this split.

**Nullable Driver Keys**: `fact_cancellations.driver_key` is nullable because trips can be cancelled before driver matching (cancellation_stage = 'requested'). Referential integrity tests must allow NULL.

**Cancellation Stage Tracking**: `fact_cancellations` captures the last state before cancellation (requested, matched, driver_en_route, driver_arrived) to analyze when in the trip lifecycle cancellations occur. Derived via window function over trip_events where trip_state != 'cancelled'.

**State Pivoting**: Trip events arrive as individual rows per state change. Fact models pivot these into single rows with columns per state timestamp (requested_at, matched_at, started_at, completed_at) using conditional aggregation with `max(case when ...)`.

**Driver Activity End Boundary**: `fact_driver_activity` excludes status periods without an end time (`where status_end is not null`). The final status period for each driver remains open-ended and is excluded from analysis to avoid incomplete duration calculations.

## Related Modules

- **[tools/dbt/models/staging](../../staging/CONTEXT.md)** — Staging models that provide cleaned event data for fact building
- **[tools/dbt/models/marts/dimensions](../dimensions/CONTEXT.md)** — Dimension tables that facts join to using temporal patterns for SCD Type 2
- **[tools/dbt/models/marts/aggregates](../aggregates/CONTEXT.md)** — Aggregate tables that roll up these facts for dashboard performance
- **[tools/dbt/tests/generic](../../../tests/generic/CONTEXT.md)** — Custom tests (fare_calculation, fee_percentage) that validate fact business rules
