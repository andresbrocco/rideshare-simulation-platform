# CONTEXT.md — Datasources

## Purpose

Grafana provisioning configuration that declares all datasources at container startup. Grafana loads this file automatically on boot, meaning datasources are never configured manually through the UI.

## Responsibility Boundaries

- **Owns**: Datasource registration, UID assignment, and cross-datasource linkage configuration
- **Delegates to**: Each backing service (Prometheus, Trino, Loki, Tempo, Airflow Postgres) for the actual data
- **Does not handle**: Dashboard definitions (managed separately under `services/grafana/dashboards/`)

## Key Concepts

All five datasources have hardcoded UIDs (`prometheus`, `trino`, `loki`, `tempo`, `airflow-postgres`). These UIDs are referenced directly in dashboard JSON panel definitions — they are not template variables. Any rename or UID change breaks every dashboard that references them.

The Trino datasource type is `trino-datasource`, a third-party plugin installed at container startup via `GF_INSTALL_PLUGINS`. It communicates over Trino's HTTP REST API (port 8080), not PostgreSQL wire protocol. The `catalog: delta` setting scopes all Trino queries to the Delta Lake catalog.

Tempo is configured with cross-datasource links: traces link to Loki logs (filtered by trace ID and span ID) and to Prometheus metrics. This enables jump-to-logs and jump-to-metrics navigation directly from a trace view.

The Airflow Postgres datasource (`airflow-postgres`) connects directly to the Airflow metadata database (`postgres-airflow:5432`, database `airflow`). It is used by the visitor activity dashboard to query `ab_user.last_login`. Credentials are injected at container startup via the `POSTGRES_AIRFLOW_USER` and `POSTGRES_AIRFLOW_PASSWORD` environment variables — the password is passed through `secureJsonData` so it is never stored in plain text in Grafana's config.

## Non-Obvious Details

- All datasources are `editable: false` — changes made in the Grafana UI are not persisted and are reverted on restart. All changes must go through this file.
- Prometheus `timeInterval: 15s` aligns with the scrape interval. Setting this too low causes misleading "no data" gaps in panels.
- The Trino datasource does not support `format: 1` (time_series) correctly for all panel types — dashboard panels that need time series from Trino must use `format: 0` (table) and handle time parsing in the query.
- The Airflow Postgres datasource uses `sslmode: disable` because `postgres-airflow` is an internal Docker/Kubernetes service not exposed over TLS. Do not enable SSL here without also configuring certificates on the Postgres container.
- `POSTGRES_AIRFLOW_USER` and `POSTGRES_AIRFLOW_PASSWORD` must be present in the Grafana container's environment at boot. If these vars are missing, the datasource will provision but all queries will fail with an authentication error.

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
