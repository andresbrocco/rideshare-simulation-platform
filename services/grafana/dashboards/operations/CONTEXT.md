# CONTEXT.md — Operations

## Purpose

Grafana dashboard (`platform-operations.json`) providing a unified operational view of the live rideshare simulation. Combines real-time simulation state from Prometheus with historical analytics from the Gold Delta Lake layer via Trino, enabling operators to monitor current platform health alongside 24-hour historical context in a single view.

## Responsibility Boundaries

- **Owns**: Operational KPI visibility — live agent counts, trip throughput, error rates, and historical performance trends
- **Delegates to**: Prometheus (real-time simulation metrics), Trino `delta.gold` catalog (historical Gold layer queries via `fact_trips`, `fact_cancellations`, `fact_ratings`, `dim_drivers`)
- **Does not handle**: Infrastructure-level metrics (CPU/memory), stream processor internals, or data quality alerts — those belong to the monitoring and data-engineering dashboards

## Key Concepts

- **Dual-datasource pattern**: Panels alternate between `uid: "prometheus"` (live state) and `uid: "trino"` (historical). Real-time panels use PromQL; historical panels use raw SQL with `rawQuery: true` and `format: 0` (table format required by the trino-datasource plugin).
- **Dashboard sections**: Four logical row groups — Real-Time Operational KPIs (stat panels), Historical Performance Gold Layer (timeseries), System Health (event/error rate), Trip State Distribution (live stats + outcome donut), Driver & Rider Activity (leaderboard table + hourly utilization barchart).
- **`simulation_offers_pending`**: Observable Gauge that emits `0` when no offers are pending (not missing data). The panel maps `null` to "N/A" to distinguish a truly absent metric from a zero value.

## Non-Obvious Details

- All Trino targets use `"format": 0` (table), not `"format": 1` (time_series). The trino-datasource plugin requires numeric format codes; string values are ignored silently.
- The "Trip Outcomes (24h)" donut chart joins `fact_trips` (completed) and `fact_cancellations` (cancelled by reason) via `UNION ALL`. Cancellation breakdowns appear as separate slices per `cancellation_reason` value — the legend reflects raw reason strings from the simulation.
- "Platform Utilization by Hour" uses a CTE with `UNNEST(ARRAY[0..23])` to guarantee all 24 hours appear even when no trips occurred, using `LEFT JOIN` + `COALESCE(..., 0)`. Without this, hours with no activity are absent from the bar chart axis.
- Driver availability threshold is operations-specific: red below 10, yellow 10–49, green 50+. This differs from any business-intelligence thresholds.
- Dashboard auto-refreshes every 5 minutes (`"refresh": "5m"`). The 24-hour time window is hardcoded (`"from": "now-24h"`), not controlled by the Grafana time picker variable.
- `simulation_errors_total` only appears in Prometheus after the first error occurs. A flat/empty error rate chart on a healthy system is expected, not a data pipeline issue.
