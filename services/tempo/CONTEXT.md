# CONTEXT.md — Tempo

## Purpose

Distributed tracing backend (Grafana Tempo 2.10.0) that receives OpenTelemetry traces from the OTel Collector and stores them in S3-compatible object storage. Enables trace-to-metrics correlation in Grafana and supports TraceQL-based trace exploration.

## Responsibility Boundaries

- **Owns**: Trace ingestion, storage, querying, and derived metric generation
- **Delegates to**: OTel Collector (trace forwarding via OTLP/gRPC), MinIO/S3 (trace block storage), Prometheus (remote-write target for derived span metrics)
- **Does not handle**: Log correlation (Loki's responsibility), metric scraping, or trace instrumentation at the application level

## Key Concepts

- **Metrics Generator**: Tempo derives Prometheus metrics directly from ingested traces. Three processors are enabled: `service-graphs` (inter-service call graphs), `span-metrics` (latency/rate/error metrics per operation), and `local-blocks` (TraceQL metrics). These are remote-written to Prometheus, enabling trace-to-metric correlation without separate instrumentation.
- **stream_over_http_enabled**: Required for the Grafana "Traces Drilldown" feature. Without this flag, streaming trace results from Tempo to Grafana fails.
- **WAL (Write-Ahead Log)**: Traces are first written to local WAL at `/var/tempo/wal` before being flushed to S3 blocks, providing durability during ingestion.

## Non-Obvious Details

- **S3 backend with LocalStack**: Storage backend is S3, but targets LocalStack (MinIO) in local development. The `insecure: true` and `forcepathstyle: true` flags are required for LocalStack compatibility; these must be removed or toggled for real AWS S3 in production.
- **Short retention**: `block_retention` is set to `1h` and `compacted_block_retention` to `10m`, intentionally minimal for local development to avoid accumulating large trace data volumes.
- **Dockerfile pattern**: The Dockerfile uses a multi-stage build to copy `wget` and `sh` from `busybox:1.37-musl` into the Tempo image, which lacks a shell and wget by default. This enables Docker health checks that call Tempo's HTTP `/ready` endpoint.
- **OTLP ingestion only**: Tempo is configured to receive traces only via OTLP/gRPC on port 4317. The OTel Collector acts as the sole ingestion point; no services send traces to Tempo directly.
- **Prometheus remote-write**: The metrics generator pushes derived metrics to `http://prometheus:9090/api/v1/write`. Prometheus must have `--web.enable-remote-write-receiver` enabled for this to work.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana](../grafana/CONTEXT.md) — Reverse dependency — Provides dashboards/monitoring/simulation-metrics.json, dashboards/data-engineering/data-ingestion.json, dashboards/data-engineering/data-quality.json (+10 more)
- [services/grafana/provisioning](../grafana/provisioning/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/provisioning/datasources](../grafana/provisioning/datasources/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/otel-collector](../otel-collector/CONTEXT.md) — Dependency — Central observability gateway routing metrics to Prometheus, logs to Loki, and t...
- [services/prometheus](../prometheus/CONTEXT.md) — Dependency — Metrics collection, alerting, and recording rule computation for the rideshare s...
