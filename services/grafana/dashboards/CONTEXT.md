# CONTEXT.md — Dashboards

## Purpose

Grafana dashboard definitions (JSON) organized by audience and concern. Each dashboard is provisioned automatically from its subdirectory and targets one or more specific observability layers of the platform.

## Responsibility Boundaries

- **Owns**: Dashboard layout, panel definitions, datasource bindings, and query logic for all Grafana views
- **Delegates to**: Grafana provisioning (`services/grafana/provisioning/`) to load and register these files at startup
- **Does not handle**: Datasource configuration, alerting rules, or data collection

## Key Concepts

**Categorical layout** — Dashboards are split into five subdirectories reflecting different audiences:
- `monitoring/` — Real-time simulation engine health (Prometheus)
- `operations/` — Unified live + historical platform state (Prometheus + Trino)
- `data-engineering/` — Bronze ingestion pipeline and Silver data quality (Trino + Prometheus)
- `business-intelligence/` — Gold layer analytics: driver/rider KPIs, revenue, demand (Trino)
- `performance/` — USE-methodology saturation and bottleneck analysis (cAdvisor via Prometheus)

**Dual-datasource pattern** — Some dashboards (`platform-operations.json`) mix Prometheus panels (real-time) and Trino panels (historical Gold/Bronze) in the same dashboard. Panels reference datasources by hardcoded UID strings (`"uid": "prometheus"` and `"uid": "trino"`), not by Grafana template variables.

**Trino plugin format** — Trino panels use the `trino-datasource` plugin (not PostgreSQL). Panel queries use `"rawQuery": true` with the SQL in `"rawSQL"` (capital SQL). Time-series panels use `"format": 0` (table format), not `"format": 1`.

## Non-Obvious Details

- `monitoring/simulation-metrics.json` uses `${DS_PROMETHEUS}` template variable references instead of the hardcoded `"uid": "prometheus"` pattern used by all other dashboards. This is the older pattern and means that dashboard requires the template variable to be defined to resolve correctly.
- `data-engineering/data-quality.json` similarly still contains `${DS_PROMETHEUS}` references mixed with hardcoded UIDs.
- The `id` field is set to `null` in all dashboards — Grafana assigns IDs at import time, so IDs should never be committed.
- `.gitkeep` files exist in `data-engineering/`, `business-intelligence/`, and `operations/` subdirectories, indicating these were intentionally created as empty placeholders before dashboards were added.

## Related Modules

- [services/grafana](../CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana](../CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning](../provisioning/CONTEXT.md) — Dependency — Grafana code-as-config provisioning: datasource registration, dashboard folder p...
- [services/grafana/provisioning](../provisioning/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/provisioning](../provisioning/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning](../provisioning/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](../provisioning/datasources/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](../provisioning/datasources/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
