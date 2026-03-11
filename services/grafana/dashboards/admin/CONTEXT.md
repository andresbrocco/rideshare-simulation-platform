# CONTEXT.md — Admin Dashboards

## Purpose

Admin-only Grafana dashboards for monitoring visitor activity across the platform. Currently contains a single unified view that aggregates per-service access timestamps for Airflow, Grafana, Simulation API, Trino, and MinIO — intended for operators to audit who accessed which platform service and when.

## Responsibility Boundaries

- **Owns**: Admin-scoped dashboard definitions (JSON provisioned into Grafana)
- **Delegates to**: `airflow-postgres` datasource for Airflow login records, `loki` datasource for all other service audit logs
- **Does not handle**: Access control enforcement, user provisioning, or log ingestion — those are the responsibility of the individual services and the Loki pipeline

## Key Concepts

- **Visitor activity**: The pattern of tracking per-visitor last-access across multiple heterogeneous services, stitched together in one dashboard rather than per-service. Each service exposes access events differently (SQL table vs. Loki log stream), and the dashboard normalizes them visually.
- **Audit log sourcing**: Each service uses a distinct mechanism — Airflow uses the `ab_user` table, Grafana uses its own audit event stream (`GF_AUDIT_ENABLED=true`), the Simulation API uses `RequestLoggerMiddleware`, Trino uses the event listener plugin emitting `QueryCompletedEvent`, and MinIO uses `MINIO_AUDIT_CONSOLE_ENABLE=on`.

## Non-Obvious Details

- Airflow logins are the only panel backed by Postgres (`airflow-postgres` datasource); all other panels query Loki using container label filters.
- The Loki query for Grafana audit events (`{container="rideshare-grafana"} |= "action=" | json`) depends on `GF_AUDIT_ENABLED=true` being set in Grafana's environment — if that flag is absent, the panel will return no results silently.
- MinIO audit events require `MINIO_AUDIT_CONSOLE_ENABLE=on` to be set on the MinIO container; the panel also returns nothing silently if this is not configured.
- Trino query events are keyed on `QueryCompletedEvent` in the log stream — events only appear after queries complete, so in-flight queries are invisible.
- The Cross-Service Activity Stream panel uses a regex container selector covering all four Loki-sourced services and shows labels, providing a unified chronological feed without deduplication.
- Dashboard refresh is set to 30s; the default time window is the last 24 hours.
- Panel IDs are all `null` — Grafana assigns IDs at provisioning time, so the JSON does not hard-code them.
