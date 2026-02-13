# CONTEXT.md — Aggregates

## Purpose

Pre-computed analytical aggregates that roll up fact tables by time and geography for dashboard performance. These tables power real-time analytics without requiring complex joins or expensive aggregations at query time.

## Responsibility Boundaries

- **Owns**: Time-series and geographic aggregations of fact tables (hourly zone demand, daily driver KPIs, daily revenue, surge history)
- **Delegates to**: Fact tables for source data, dimension tables for foreign key validation
- **Does not handle**: Real-time streaming aggregates (those come from stream-processor), single-trip analysis (use fact tables directly), ad-hoc custom aggregations

## Key Concepts

**Grain Consistency**: Each aggregate has a well-defined grain (zone+hour, driver+day, zone+day) that determines uniqueness. Mixing grains in joins requires careful consideration.

**Completion Rate Alignment**: `agg_hourly_zone_demand` uses `requested_at` for both requests and completions to ensure `completed_trips <= requested_trips` within the same hour bucket. This avoids race conditions where a trip requested at 2:59pm completes at 3:01pm.

**Utilization Calculation**: Driver utilization in `agg_daily_driver_performance` is `(en_route_minutes + on_trip_minutes) / online_minutes * 100`. The denominator is online time, not calendar time. Tests enforce utilization stays between 0-100%.

**Revenue Consistency**: `agg_daily_platform_revenue` enforces `total_revenue = platform_fees + driver_payouts` with a custom test allowing 0.01 margin for floating point precision. The 25%/75% split is calculated in `fact_payments`, not here.

## Non-Obvious Details

**Full Outer Join for Demand**: `agg_hourly_zone_demand` uses a full outer join between requests and completions because some hours may have only requests (no completions) or only completions (no requests in that hour). This ensures no data loss.

**Surge History Uses Raw Events**: `agg_surge_history` joins to `stg_surge_updates` instead of facts because surge updates occur independently of trips. A zone can have surge changes without any trips occurring.

**Wait Time Definition**: Wait time in `agg_hourly_zone_demand` is `(started_at - matched_at)`, representing the time between driver acceptance and trip start, not request-to-match time.

**Coalesce Defaults**: All aggregates use `coalesce(..., 0)` for counts and sums to handle NULL values in joins. Division operations check for zero denominators explicitly to return 0.0 instead of NULL or error.

## Related Modules

- **[tools/dbt/models/marts/facts](../facts/CONTEXT.md)** — Source fact tables that aggregates roll up; fact grain determines aggregate granularity possibilities
- **[tools/dbt/models/marts/dimensions](../dimensions/CONTEXT.md)** — Dimension tables joined for descriptive attributes in aggregates
- **[services/grafana](../../../../services/grafana/CONTEXT.md)** — Primary consumer of aggregates via Trino datasource; dashboards query these pre-computed tables for performance
- **[tools/great-expectations](../../../great-expectations/CONTEXT.md)** — Validates aggregate data quality including revenue consistency and utilization bounds
