# CONTEXT.md — Monitoring

## Purpose

Observability stack for the rideshare simulation platform using Prometheus for metrics collection and Grafana for visualization and alerting. Monitors data pipeline health (Kafka, Spark, Airflow) and container resource utilization across all services.

## Responsibility Boundaries

- **Owns**: Metrics collection configuration, scrape targets, alert rule definitions, dashboard provisioning
- **Delegates to**: Prometheus for time-series storage, Grafana for visualization, cAdvisor for container metrics
- **Does not handle**: Application-level logging (handled by service-specific structured logging), distributed tracing

## Key Concepts

**Scrape Targets**: Prometheus actively polls metrics endpoints every 15-30 seconds from statically-defined targets (cadvisor, kafka, spark-master, spark-worker, airflow-webserver).

**Provisioning**: Grafana is configured entirely via GitOps-friendly YAML files rather than manual UI configuration. Datasources, dashboards, and alert rules are auto-loaded on startup.

**Alert Groups**: Two distinct groups separate pipeline failures (critical, 1-minute evaluation) from resource thresholds (warning, longer toleration windows).

**7-Day Retention**: Metrics are retained for one week in Prometheus TSDB. This trades long-term historical analysis for lower storage requirements in local development.

## Non-Obvious Details

The monitoring stack runs under Docker Compose's `monitoring` profile, which is independent of the `core` and `data-pipeline` profiles. This allows starting simulation services without incurring the memory overhead of Prometheus (512MB) and Grafana (192MB).

Grafana alert rules use Prometheus datasource UID references and must match the datasource name configured in `provisioning/datasources/prometheus.yml`. Dashboard JSON files contain template variables that are auto-populated from Prometheus queries.

Container-specific alerts (Kafka, Spark) use naming conventions from Docker Compose service names (e.g., `rideshare-kafka`, `rideshare-spark-.*`) to filter cAdvisor container metrics.

Prometheus self-monitors via the `prometheus` scrape target at `localhost:9090`, enabling detection of Prometheus downtime through the `PrometheusDown` alert rule.

## Related Modules

- **[infrastructure/kubernetes](../kubernetes/CONTEXT.md)** — Both provide infrastructure deployment; monitoring observes services deployed via K8s or Docker Compose
- **[analytics/superset](../../analytics/superset/CONTEXT.md)** — Complementary visualization; Grafana visualizes infrastructure metrics, Superset visualizes business analytics
- **[services/simulation/src/api/routes](../../services/simulation/src/api/routes/CONTEXT.md)** — Exposes /metrics endpoints that Prometheus scrapes for simulation performance data
