# CONTEXT.md — Grafana Provisioning

## Purpose

Declares Grafana's runtime configuration as code: datasource connections, dashboard folder providers, and alerting rules. These files are loaded by Grafana at startup and on a polling interval, making configuration reproducible without manual UI setup.

## Responsibility Boundaries

- **Owns**: Datasource registration, dashboard folder-to-path mappings, alerting rule definitions
- **Delegates to**: `services/grafana/dashboards/` for the actual dashboard JSON files
- **Does not handle**: Dashboard content, Grafana plugin installation (done via `GF_INSTALL_PLUGINS` env var), or Grafana user/org management

## Key Concepts

**Datasource UIDs**: All datasources are assigned hardcoded UIDs (`prometheus`, `trino`, `loki`, `tempo`, `airflow-postgres`). Dashboard JSON files reference these UIDs directly — using template variables like `${DS_PROMETHEUS}` is intentionally avoided. This means UIDs must never be changed without updating all dashboard files.

**Trino datasource type**: Uses `trino-datasource` plugin (not a PostgreSQL-compatible plugin). This plugin communicates via Trino's HTTP REST API (port 8080 inside the network), not the PostgreSQL wire protocol. The catalog is set to `delta`.

**Tempo cross-datasource linking**: Tempo is configured with `tracesToLogsV2` pointing to Loki (by UID) and `tracesToMetrics` pointing to Prometheus. This enables trace-to-log and trace-to-metric correlation within the Grafana UI.

**Dashboard providers**: `dashboards/default.yml` maps six named folders to filesystem paths under `/etc/dashboards/` (monitoring, data-engineering, business-intelligence, performance, operations, admin). Grafana polls each path every 10 seconds for JSON changes. `allowUiUpdates: true` permits in-browser edits (they persist in the container until restart but are not written back to disk). The `admin` folder at `/etc/dashboards/admin` holds dashboards restricted to org admins, such as the visitor activity dashboard.

## Non-Obvious Details

- Alert `noDataState: NoData` means an alert fires only when data is present and the condition is met — it does not fire when a metric series is absent. This is intentional for counters like `simulation_errors_total` that only appear after the first error event.
- Alert `execErrState: Alerting` means a Prometheus query error triggers the alert rather than silencing it — chosen to avoid hiding connectivity failures.
- The `alerting/rules.yml` folder assignment (`folder: Monitoring`) is separate from the dashboard folder providers; it controls where Grafana stores the alert rule in its UI, not a filesystem path.
- Prometheus datasource `timeInterval: 15s` matches the scrape interval configured in `services/prometheus/prometheus.yml`. Mismatching these causes incorrect rate calculations in PromQL.
- The `airflow-postgres` datasource uses the standard PostgreSQL datasource type (not `trino-datasource`) and connects to `postgres-airflow:5432`. Unlike the other four UIDs which are single lowercase words, its UID is the hyphenated string `airflow-postgres`. Credentials are injected via `POSTGRES_AIRFLOW_USER` / `POSTGRES_AIRFLOW_PASSWORD` env vars with `sslmode: disable` — internal service, no TLS configured.

## Related Modules

- [services/grafana](../CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana](../CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/dashboards](../dashboards/CONTEXT.md) — Dependency — Grafana dashboard JSON definitions organized by audience (monitoring, operations...
- [services/grafana/dashboards](../dashboards/CONTEXT.md) — Reverse dependency — Provides monitoring/simulation-metrics.json, operations/platform-operations.json, data-engineering/data-ingestion.json (+7 more)
- [services/grafana/dashboards](../dashboards/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/dashboards](../dashboards/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](datasources/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](datasources/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/prometheus](../../prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/tempo](../../tempo/CONTEXT.md) — Dependency — Distributed tracing backend storing OpenTelemetry traces and deriving span metri...
- [services/trino](../../trino/CONTEXT.md) — Dependency — Trino SQL query engine configuration and startup scripting for Delta Lake access...
