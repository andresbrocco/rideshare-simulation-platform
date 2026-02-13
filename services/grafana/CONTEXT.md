# CONTEXT.md — Grafana

## Purpose

Visualization and alerting service providing multi-datasource observability for the rideshare simulation platform. Offers pre-provisioned dashboards spanning operational monitoring, data engineering, and business intelligence, with alert rules for simulation health and resource thresholds.

## Responsibility Boundaries

- **Owns**: Dashboard JSON definitions across 4 categories (monitoring, data-engineering, business-intelligence, operations), datasource provisioning for 4 backends (Prometheus, Trino, Loki, Tempo), alert rule configuration, provisioning manifests
- **Delegates to**: Prometheus for metrics storage, Trino for lakehouse queries, Loki for log aggregation, Tempo for distributed tracing
- **Does not handle**: Metrics collection, log ingestion, trace collection, container orchestration

## Key Concepts

**GitOps Provisioning**: All configuration is file-based. Datasources, dashboards, and alert rules are auto-loaded on startup from `provisioning/` subdirectories, eliminating manual UI configuration.

**Multi-Datasource Architecture**: Four distinct datasources with specialized roles — Prometheus (metrics), Trino (Delta Lake queries via HTTP REST), Loki (logs), Tempo (traces with correlation to logs/metrics).

**Dashboard Categories**: Four organizational folders — Monitoring (simulation-metrics), Data Engineering (data-ingestion, data-quality), Business Intelligence (demand-analysis, driver-performance, revenue-analytics), Operations (platform-operations).

**Alert Groups**: Two groups — `resource_thresholds` (warning severity, memory/CPU thresholds for simulation, stream-processor, kafka) and `simulation_alerts` (critical severity, error rates, Kafka/Redis disconnections).

**Datasource UID References**: Alert rules and dashboard panels reference datasources by UID (prometheus, trino, loki, tempo), which must match names in `provisioning/datasources/datasources.yml`.

## Non-Obvious Details

Runs under Docker Compose's `monitoring` profile with 384MB memory limit. Default credentials are admin/admin. Container serves on port 3000 internally, mapped to host port 3001 to avoid conflicts.

Trino datasource uses `trino-datasource` plugin (installed via `GF_INSTALL_PLUGINS` env var), NOT PostgreSQL plugin. Queries use HTTP REST API at port 8080, not PostgreSQL wire protocol. Dashboard queries must use numeric `"format": 0` (table) or `"format": 1` (time_series), not string values.

Container-specific alerts use Docker Compose service name patterns (e.g., `rideshare-simulation`, `rideshare-kafka`) to filter cAdvisor metrics.

Dashboard provisioning allows UI updates (`allowUiUpdates: true`) for development, with 10-second refresh interval to detect new JSON files.

## Related Modules

- **[services/grafana/provisioning/datasources](provisioning/datasources/CONTEXT.md)** — Datasource configuration that Grafana auto-loads; defines connections to Prometheus, Trino, Loki, and Tempo
- **[services/prometheus](../prometheus/CONTEXT.md)** — Primary metrics datasource for operational monitoring dashboards; provides time-series data for alerts
- **[tools/dbt/models/marts](../../tools/dbt/models/marts/CONTEXT.md)** — Gold layer tables queried via Trino datasource for business intelligence dashboards
- **[infrastructure/scripts](../../infrastructure/scripts/CONTEXT.md)** — Exports DBT Gold tables to S3 that Trino queries for dashboard visualizations
