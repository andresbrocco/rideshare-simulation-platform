# CONTEXT.md — Loki

## Purpose

Configuration for the Grafana Loki log aggregation backend. Loki stores and indexes logs collected by the OpenTelemetry Collector, providing LogQL-based querying for the rideshare simulation platform's observability stack.

## Responsibility Boundaries

- **Owns**: Log storage, log indexing (TSDB schema v13), log querying via LogQL, retention enforcement (7 days)
- **Delegates to**: OTel Collector for log collection, parsing, and label enrichment before push; Grafana for log visualization and exploration
- **Does not handle**: Log collection from containers (OTel Collector's filelog receiver), log instrumentation in application code, alerting rules (Grafana)

## Key Concepts

**Single-Node Mode**: Loki runs with `inmemory` ring membership for single-node deployment. All components (ingester, distributor, querier, compactor) run in the same process. No clustering coordination needed.

**TSDB Index Schema (v13)**: Uses the latest TSDB-based index format (`schema: v13`) with filesystem storage. Index and chunks are stored under `/loki/` inside the container. This is the recommended schema for new Loki deployments.

**7-Day Retention**: `retention_period: 168h` with compaction-based deletion. The compactor runs retention enforcement, cleaning up chunks and index entries older than 7 days.

**Push-Based Ingestion**: Loki does not pull logs. The OTel Collector pushes structured log entries to `http://loki:3100/loki/api/v1/push` with Loki-compatible labels (level, service_name, container_id).

## Non-Obvious Details

Loki is label-oriented, not full-text indexed. High-cardinality labels (e.g., request IDs, user IDs) should not be promoted to Loki labels — they cause index explosion. The OTel Collector config controls which attributes become labels via `loki.attribute.labels` hints.

The retention window of 168 hours is enforced by the compactor. Note that `reject_old_samples` and `reject_old_samples_max_age` are not currently configured in `loki-config.yaml`.
