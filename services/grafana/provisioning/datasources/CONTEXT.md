# CONTEXT.md — Datasources

## Purpose

Grafana datasource provisioning configuration defining 4 observability backends for multi-source visualization. Enables automatic datasource registration on Grafana startup without manual UI configuration.

## Responsibility Boundaries

- **Owns**: Datasource definitions for Prometheus (metrics), Trino (lakehouse queries), Loki (logs), Tempo (traces), connection URLs, plugin types, cross-datasource correlation configuration
- **Delegates to**: Grafana server for datasource registration, underlying backends for actual data storage and query execution
- **Does not handle**: Metrics collection, log ingestion, trace collection, dashboard definitions, alert rules

## Key Concepts

**Multi-Datasource Observability**: Four specialized backends serving distinct query patterns — Prometheus (time-series metrics), Trino (SQL on Delta Lake via HTTP REST), Loki (log aggregation), Tempo (distributed tracing with correlation).

**Datasource UID System**: Each datasource has a unique identifier (prometheus, trino, loki, tempo) referenced by dashboards and alert rules. UIDs must remain stable across restarts to preserve dashboard references.

**Cross-Datasource Correlation**: Tempo is configured to link traces to logs (via Loki) and metrics (via Prometheus), enabling navigation from trace spans to related logs and performance metrics. Uses `tracesToLogsV2` and `tracesToMetrics` JSON configuration.

**GitOps Provisioning**: File-based configuration auto-loaded by Grafana on startup. Changes require container restart. All datasources are marked `editable: false` to enforce configuration-as-code.

## Non-Obvious Details

Trino datasource uses `trino-datasource` plugin (not PostgreSQL plugin) and communicates via HTTP REST API on port 8080, not PostgreSQL wire protocol. The plugin must be installed via Grafana's `GF_INSTALL_PLUGINS` environment variable.

Prometheus is marked as default datasource (`isDefault: true`). This determines which datasource is pre-selected in dashboard query editors.

Tempo's `nodeGraph` and `serviceMap` features are enabled to visualize trace topology. Service map uses Prometheus as its metrics datasource to show request rates and error percentages.

All URLs use Docker Compose service names as hostnames (prometheus:9090, trino:8080, loki:3100, tempo:3200), which resolve via Docker's internal DNS.

## Related Modules

- **[services/prometheus](../../../prometheus/CONTEXT.md)** — Metrics backend that this datasource configuration connects to; scrapes simulation and infrastructure metrics
- **[tools/dbt/models/marts](../../../../tools/dbt/models/marts/CONTEXT.md)** — Gold layer tables accessible via Trino datasource for business intelligence queries
- **[services/grafana](../../CONTEXT.md)** — Parent service that loads this datasource configuration during startup provisioning
