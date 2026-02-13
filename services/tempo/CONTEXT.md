# CONTEXT.md — Tempo

## Purpose

Configuration for the Grafana Tempo distributed tracing backend. Tempo stores and indexes traces collected by the OpenTelemetry Collector, providing TraceQL-based querying and generating span metrics for the rideshare simulation platform's observability stack.

## Responsibility Boundaries

- **Owns**: Trace storage (local WAL at `/var/tempo`), trace querying via TraceQL, metrics generation from traces (span metrics and service graphs)
- **Delegates to**: OTel Collector for trace collection and forwarding via OTLP gRPC, Grafana for trace visualization and Traces Drilldown, Prometheus for storing generated span metrics and service graphs
- **Does not handle**: Trace instrumentation (done by application services via OpenTelemetry SDK), trace collection/routing (OTel Collector), alerting, dashboards (Grafana)

## Key Concepts

**OTLP gRPC Ingestion**: Traces arrive from the OTel Collector via OTLP gRPC on port 4317 (mapped to 4319 on host to avoid conflict with the OTel Collector's own port 4317).

**Metrics Generator**: Tempo generates two types of metrics from ingested traces:
- **Span metrics** — Histograms and counters derived from span attributes (latency, error rates)
- **Service graphs** — Relationship metrics between services for dependency visualization

Both are pushed to Prometheus via remote write (`http://prometheus:9090/api/v1/write`).

**Stream Over HTTP**: `stream_over_http_enabled: true` enables streaming trace results to Grafana, required for the Traces Drilldown feature to function properly.

**Local WAL Storage**: Traces are written to a write-ahead log at `/var/tempo/wal` before being flushed to block storage at `/var/tempo/blocks`. Single-node mode with no external object store.

## Non-Obvious Details

The Dockerfile copies `wget` from a busybox stage because the base `grafana/tempo` image does not include it. Docker Compose uses `wget` for the container health check (`wget --no-verbose --tries=1 --spider http://localhost:3200/ready`).

The `metrics_generator` remote write target must match the Prometheus service name in Docker Compose. If Prometheus is not running, Tempo will log remote write errors but continue to function for trace storage.
