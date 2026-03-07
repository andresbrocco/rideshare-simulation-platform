# CONTEXT.md — Singular Tests

## Purpose

Domain-level DBT singular tests that validate cross-model business invariants for the rideshare platform. Unlike generic schema tests (not-null, unique), these encode business rules that require multi-column logic or domain-specific thresholds.

## Responsibility Boundaries

- **Owns**: Business invariant validation across Gold-layer aggregate and fact models
- **Delegates to**: `schema.yml` generic tests for column-level constraints (not-null, uniqueness, accepted values)
- **Does not handle**: Data freshness checks, row count assertions, or Silver-layer validation (those belong to Great Expectations)

## Key Concepts

- **Singular test semantics**: DBT singular tests pass when the query returns zero rows. Any returned row is a test failure, so all queries are written to SELECT only the violating records.
- **Surge multiplier bounds**: Valid surge multipliers are in the range [1.0, 2.5]. `test_surge_multiplier_range.sql` also enforces internal consistency — `min_surge_multiplier` must not exceed `avg_surge_multiplier`, and `max_surge_multiplier` must not be below it.
- **Revenue split invariant**: Platform fee is exactly 25% of `total_fare` (within $0.01 rounding tolerance). Driver payout plus platform fee must equal `total_fare` exactly (within $0.001). These constants are part of the simulated business model.
- **Driver idle bounds**: `online_minutes` in `agg_daily_driver_performance` represents total logged-in time across ALL statuses (`available`, `offline`, `en_route_pickup`, `on_trip`, `driving_closer_to_home`), not just idle time. The test enforces that `en_route_minutes + on_trip_minutes <= online_minutes` and that `idle_pct` stays within [0.0, 100.0].

## Non-Obvious Details

- The `online_minutes >= en_route_minutes + on_trip_minutes` invariant is easy to break if `online_minutes` is incorrectly computed as only the `available` status duration. The definition is total session time regardless of sub-state.
- Revenue tolerances differ intentionally: the fee-split sum check uses $0.001 (strict — should be exact), while the 25% fee-proportion check uses $0.01 (lenient — floating-point multiplication can introduce rounding).

## Related Modules

- [tools/dbt/models/marts/aggregates](../../models/marts/aggregates/CONTEXT.md) — Dependency — Pre-aggregated analytical models rolling up Gold-layer facts into time-bucketed ...
- [tools/dbt/models/marts/facts](../../models/marts/facts/CONTEXT.md) — Dependency — Gold-layer fact tables for the rideshare star schema covering completed trips, p...
