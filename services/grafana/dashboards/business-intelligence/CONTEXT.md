# CONTEXT.md — Business Intelligence Dashboards

## Purpose

Grafana dashboards targeting business stakeholders rather than platform operators. All dashboards query the Gold layer star schema via the `trino-datasource` plugin to surface rideshare KPIs: driver workforce performance, revenue analytics, demand patterns, and per-entity deep-dives for individual drivers and riders.

## Responsibility Boundaries

- **Owns**: Business-facing analytics views over the Gold layer; defining which Gold tables and computed metrics constitute the BI surface
- **Delegates to**: `delta.gold.*` tables (via Trino) for all data; the `agg_daily_driver_performance` aggregate table for driver efficiency metrics
- **Does not handle**: Operational observability (see `monitoring/`), data engineering pipeline metrics (see `data-engineering/`), or real-time simulation state

## Key Concepts

**Gold layer tables used**: `fact_trips`, `fact_ratings`, `fact_payments`, `dim_drivers`, `dim_riders`, `dim_time`, `agg_daily_driver_performance`. All queries use raw SQL with `rawQuery: true` and `format: 0` (table format, required by the Trino datasource plugin).

**SCD Type 2 dimension filtering**: Queries against `dim_drivers` and `dim_riders` must include `AND current_flag = TRUE` to select only the active dimension record. Omitting this produces duplicate rows across historical versions.

**Explorer dashboards**: `driver-explorer.json` and `rider-explorer.json` use Grafana template variables (`$driver_id`, `$rider_id`) to scope all panels to a single entity. These are deep-dive dashboards meant for selecting a specific agent and exploring their full history.

**7-day lookback convention**: Aggregate dashboards (`driver-performance.json`, `revenue-analytics.json`, `demand-analysis.json`) apply a uniform `INTERVAL '7' DAY` lookback using `current_timestamp` or `current_date` as the anchor. This is a fixed window, not a Grafana time-picker range.

**idle_pct definition**: In `agg_daily_driver_performance`, `idle_pct` represents the ratio of `available` (non-trip) time to total online time — it is NOT the ratio of offline time to total time. A higher value means the driver was online but unproductive.

## Non-Obvious Details

- All Trino targets use `"rawQuery": true` and `"rawSQL"` (capital SQL) with `"format": 0`. The Trino datasource plugin does not support Grafana's standard query builder or `"format": 1` (time series); time series panels are constructed by returning a timestamp column and using table format.
- Datasource is always hardcoded as `{"type": "trino-datasource", "uid": "trino"}`. Template variables for datasources (`${DS_*}`) are intentionally avoided per project conventions.
- `fact_trips` contains all trip states (requested, matched, completed, cancelled). Panels that count only completed trips must filter `trip_state = 'completed'`; panels measuring raw demand count all states.
- `fact_ratings` covers both driver and rider ratings in a single table; the `ratee_type` column (`'driver'` or `'rider'`) must be used to filter to the relevant party.
- `fact_payments` separates `driver_payout` from `platform_fee` — revenue analytics must sum the correct column depending on whether the view is driver earnings or platform revenue.
