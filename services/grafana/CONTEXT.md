# CONTEXT.md — Grafana

## Purpose

Visualization and alerting service for the rideshare simulation platform. Provides pre-provisioned dashboards for Kafka, Spark, and Airflow metrics collected by Prometheus, plus alert rules for pipeline failures and resource thresholds.

## Responsibility Boundaries

- **Owns**: Dashboard JSON definitions, datasource provisioning, alert rule configuration, dashboard provisioning config
- **Delegates to**: Prometheus for metrics storage and querying, Docker Compose for deployment orchestration
- **Does not handle**: Metrics collection (Prometheus), container metrics export (cAdvisor)

## Key Concepts

**GitOps Provisioning**: All configuration is file-based rather than manual UI clicks. Datasources, dashboards, and alert rules are auto-loaded on startup from `provisioning/` subdirectories.

**Dashboard Provisioning**: JSON dashboard files in `dashboards/` are discovered via `provisioning/dashboards/default.yml`. Template variables in dashboards are auto-populated from Prometheus queries.

**Alert Groups**: Two distinct alert groups — pipeline failures (critical, 1-minute evaluation: Kafka lag, Spark failures, Airflow DAG failures) and resource thresholds (warning, longer toleration windows: memory, CPU).

**Datasource UID References**: Alert rules reference the Prometheus datasource by UID, which must match the name configured in `provisioning/datasources/prometheus.yml`.

## Non-Obvious Details

Runs under Docker Compose's `monitoring` profile with 384MB memory limit. Default credentials are admin/admin. The container serves on port 3000 internally, mapped to host port 3001 to avoid conflicts.

Container-specific alerts use naming conventions from Docker Compose service names (e.g., `rideshare-kafka`, `rideshare-spark-.*`) to filter cAdvisor container metrics via Prometheus queries.

## Related Modules

- **[services/prometheus](../prometheus/CONTEXT.md)** — Sole datasource; all Grafana dashboards and alerts query Prometheus metrics
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Grafana container, volume mounts, and monitoring profile
