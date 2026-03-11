# CONTEXT.md — Grafana

## Purpose

Grafana serves as the unified observability frontend for the rideshare simulation platform, aggregating metrics, logs, traces, analytical query results, and operator audit data across five datasources. It exposes dashboards organized by data layer (Monitoring, Data Engineering, Business Intelligence, Operations, Performance, Admin) and hosts alerting rules for infrastructure and simulation health.

## Responsibility Boundaries

- **Owns**: Dashboard definitions (JSON), datasource provisioning, alerting rule provisioning, dashboard folder organization
- **Delegates to**: Prometheus (metrics), Loki (logs), Tempo (distributed traces), Trino (Delta Lake SQL analytics), PostgreSQL/Airflow (operator audit queries via `airflow-postgres` datasource)
- **Does not handle**: Metric collection, log shipping, trace generation, or data transformation — all data is read-only from upstream sources

## Key Concepts

**Dashboard folders by data layer**: Dashboards are partitioned into six Grafana folders that map to the platform's layered architecture:
- `Monitoring` — real-time simulation engine metrics (Prometheus source)
- `Data Engineering` — Bronze/Silver pipeline health (Trino + Prometheus sources)
- `Business Intelligence` — Gold star schema analytics (Trino source)
- `Operations` — platform-wide operational view
- `Performance` — performance engineering metrics
- `Admin` — operator-only dashboards for visitor activity auditing (airflow-postgres + Loki sources)

**Multi-datasource fan-out**: A single dashboard may mix Prometheus panels (real-time) and Trino panels (historical/analytical). Datasource UIDs are hardcoded (`prometheus`, `trino`, `loki`, `tempo`, `airflow-postgres`) rather than using template variables (`${DS_*}`) — this is intentional to avoid provisioning-time resolution issues.

**Trino datasource plugin**: The `trino-datasource` plugin (installed via `GF_INSTALL_PLUGINS`) communicates via Trino's HTTP REST API (port 8080 in-container). It is not the PostgreSQL wire protocol. All Trino panels must set `"rawQuery": true` and use `"rawSQL"` (capital SQL) for the query field. The numeric format field `"format": 0` means table output; `"format": 1` means time series — string values are rejected.

**Tempo cross-datasource linking**: Tempo is configured with `tracesToLogsV2` (linked to Loki, filtered by trace/span ID) and `tracesToMetrics` (linked to Prometheus), enabling drill-down from a trace to correlated logs and metrics.

## Non-Obvious Details

- Dashboards in `dashboards/data-engineering/` and `dashboards/business-intelligence/` currently contain `.gitkeep` placeholders alongside JSON files — the `.gitkeep` files coexist with provisioned dashboards and do not affect Grafana loading.
- `simulation_errors_total`, `stream_processor_validation_errors_total`, and `simulation_corrupted_events_total` only appear in Prometheus after the first error event. On a healthy system these metrics are absent entirely, not zero — panels relying on them will show "No data" rather than 0.
- `simulation_offers_pending` is an Observable Gauge (not UpDownCounter). It emits 0 when no offers are pending, so a zero reading is normal, not an absent metric.
- Redis latency panels should source from `stream_processor_redis_publish_latency_seconds_bucket`; the metric `simulation_redis_latency_seconds_bucket` does not exist in the simulation service.
- Alert rules use `noDataState: NoData` (not `OK`), so missing metrics during startup do not trigger false alerts.
- The Trino catalog is set to `delta` in the datasource provisioning — all SQL queries reference tables in the `delta` catalog without needing to qualify the catalog name explicitly.
- The `airflow-postgres` datasource (uid: `airflow-postgres`) uses the standard PostgreSQL datasource type (not `trino-datasource`) and connects to the `airflow-postgres` service on port 5432. It is required by `dashboards/admin/visitor-activity.json` for Airflow login/audit panels.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/dashboards](dashboards/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/dashboards](dashboards/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning](provisioning/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning](provisioning/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](provisioning/datasources/CONTEXT.md) — Shares Observability and Metrics domain (hardcoded datasource uids)
- [services/grafana/provisioning/datasources](provisioning/datasources/CONTEXT.md) — Shares Grafana Dashboards and Visualization domain (hardcoded datasource uids)
- [services/prometheus](../prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
- [services/tempo](../tempo/CONTEXT.md) — Dependency — Distributed tracing backend storing OpenTelemetry traces and deriving span metri...
- [services/trino](../trino/CONTEXT.md) — Dependency — Trino SQL query engine configuration and startup scripting for Delta Lake access...
