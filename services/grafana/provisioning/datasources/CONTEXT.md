# CONTEXT.md — Datasources

## Purpose

Grafana provisioning configuration that declares all datasources at container startup. Grafana loads this file automatically on boot, meaning datasources are never configured manually through the UI.

## Responsibility Boundaries

- **Owns**: Datasource registration, UID assignment, and cross-datasource linkage configuration
- **Delegates to**: Each backing service (Prometheus, Trino, Loki, Tempo) for the actual data
- **Does not handle**: Dashboard definitions (managed separately under `services/grafana/dashboards/`)

## Key Concepts

All four datasources have hardcoded UIDs (`prometheus`, `trino`, `loki`, `tempo`). These UIDs are referenced directly in dashboard JSON panel definitions — they are not template variables. Any rename or UID change breaks every dashboard that references them.

The Trino datasource type is `trino-datasource`, a third-party plugin installed at container startup via `GF_INSTALL_PLUGINS`. It communicates over Trino's HTTP REST API (port 8080), not PostgreSQL wire protocol. The `catalog: delta` setting scopes all Trino queries to the Delta Lake catalog.

Tempo is configured with cross-datasource links: traces link to Loki logs (filtered by trace ID and span ID) and to Prometheus metrics. This enables jump-to-logs and jump-to-metrics navigation directly from a trace view.

## Non-Obvious Details

- All datasources are `editable: false` — changes made in the Grafana UI are not persisted and are reverted on restart. All changes must go through this file.
- Prometheus `timeInterval: 15s` aligns with the scrape interval. Setting this too low causes misleading "no data" gaps in panels.
- The Trino datasource does not support `format: 1` (time_series) correctly for all panel types — dashboard panels that need time series from Trino must use `format: 0` (table) and handle time parsing in the query.

## Related Modules

- [services/grafana](../../CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana](../../CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/dashboards](../../dashboards/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/dashboards](../../dashboards/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning](../CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning](../CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/prometheus](../../../prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/tempo](../../../tempo/CONTEXT.md) — Dependency — Distributed tracing backend storing OpenTelemetry traces and deriving span metri...
- [services/trino](../../../trino/CONTEXT.md) — Dependency — Trino SQL query engine configuration and startup scripting for Delta Lake access...
