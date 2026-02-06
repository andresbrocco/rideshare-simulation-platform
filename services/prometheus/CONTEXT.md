# CONTEXT.md — Prometheus

## Purpose

Metrics collection and storage service for the rideshare simulation platform. Actively scrapes metrics endpoints from all instrumented services and stores time-series data for querying by Grafana dashboards and alert evaluation.

## Responsibility Boundaries

- **Owns**: Scrape target configuration, alert rule definitions, metrics retention policy, PromQL query engine
- **Delegates to**: Grafana for visualization and alerting UI, cAdvisor for container metrics export, individual services for metrics endpoint implementation
- **Does not handle**: Visualization (Grafana), container metrics collection (cAdvisor), application logging, distributed tracing

## Key Concepts

**Scrape Targets**: Prometheus actively polls metrics endpoints every 15-30 seconds from statically-defined targets — prometheus (self), cadvisor, kafka, spark-master, spark-worker, airflow-webserver.

**Alert Rules**: Defined in `rules/alerts.yml` with two groups — Prometheus health (PrometheusDown, PrometheusScrapeFailure) and container health (HighContainerMemoryUsage, ContainerDown).

**7-Day Retention**: Metrics are retained for one week in Prometheus TSDB (`--storage.tsdb.retention.time=7d`). This trades long-term historical analysis for lower storage requirements in local development.

**Self-Monitoring**: Prometheus scrapes its own `/metrics` endpoint via the `prometheus` job at `localhost:9090`, enabling detection of Prometheus downtime through the `PrometheusDown` alert rule.

## Non-Obvious Details

Runs under Docker Compose's `monitoring` profile with 512MB memory limit. Configuration is mounted read-only from `prometheus.yml` and `rules/` directory.

The `--web.enable-lifecycle` flag enables hot-reloading of configuration via `POST http://localhost:9090/-/reload` without container restart.

Scrape targets reference Docker Compose service names (e.g., `cadvisor:8080`, `kafka:9092`) which resolve via the shared Docker network.

## Related Modules

- **[services/grafana](../grafana/CONTEXT.md)** — Primary consumer; all Grafana dashboards query Prometheus as their datasource
- **[services/simulation/src/api/routes](../simulation/src/api/routes/CONTEXT.md)** — Exposes /metrics endpoints that Prometheus scrapes for simulation performance data
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Prometheus container, volume mounts, and monitoring profile
