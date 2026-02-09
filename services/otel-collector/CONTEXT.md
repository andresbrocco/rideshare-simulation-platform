# CONTEXT.md — OpenTelemetry Collector

## Purpose

Configuration for the OpenTelemetry Collector Contrib, the central telemetry pipeline that routes metrics, logs, and traces between application services and observability backends. All telemetry data flows through this collector before reaching Prometheus, Loki, or Tempo.

## Responsibility Boundaries

- **Owns**: Telemetry routing (3 pipelines: metrics, logs, traces), Docker container log parsing and enrichment, Loki label management via attribute hints, collector self-metrics
- **Delegates to**: Loki for log storage and querying, Tempo for trace storage and querying, Prometheus for metrics storage and querying, Grafana for visualization and dashboards
- **Does not handle**: Log/trace/metric generation (done by application services via OpenTelemetry SDK), dashboards or alerting (Grafana), long-term storage configuration (each backend manages its own)

## Key Concepts

**Three Pipelines**: The collector runs three independent pipelines, each with its own receivers, processors, and exporters:

| Pipeline | Receiver | Exporter | Purpose |
|----------|----------|----------|---------|
| metrics | OTLP (gRPC/HTTP) | Prometheus remote write | Application metrics → Prometheus |
| logs | filelog (Docker JSON) | Loki push API | Container logs → Loki |
| traces | OTLP (gRPC/HTTP) | OTLP gRPC | Application traces → Tempo |

**Filelog Receiver**: Reads Docker container JSON log files from `/var/lib/docker/containers/*/*-json.log`. Uses JSON operators to extract `log`, `time`, `stream`, and `attrs` fields. A `move` operator maps the extracted body to the log record body.

**Loki Label Hints**: The `loki.attribute.labels` resource attribute controls which attributes are promoted to Loki index labels. Currently promotes: `level`, `service`, `service_name`, `container_id`. Adding high-cardinality attributes here would cause Loki index explosion.

**Root User Requirement**: Runs as `user: "0:0"` to access the Docker socket (`/var/run/docker.sock`) and read container log files under `/var/lib/docker/containers/`.

## Non-Obvious Details

The Dockerfile copies `wget` from a busybox stage because the base `otel/opentelemetry-collector-contrib` image does not include it. Docker Compose uses `wget` for the container health check.

The OTLP receiver listens on ports 4317 (gRPC) and 4318 (HTTP). Application services send telemetry to these ports. Tempo also receives OTLP, but on different host-mapped ports (4319) to avoid conflicts.

Port 8888 exposes the collector's own internal metrics (pipeline throughput, dropped data, queue sizes). Port 13133 is the dedicated health check extension endpoint.

## Related Modules

- **[services/loki](../loki/CONTEXT.md)** — Receives parsed and enriched logs via Loki push API
- **[services/tempo](../tempo/CONTEXT.md)** — Receives traces via OTLP gRPC export
- **[services/prometheus](../prometheus/CONTEXT.md)** — Receives application metrics via Prometheus remote write
- **[services/simulation](../simulation/CONTEXT.md)** — Produces metrics and traces via OpenTelemetry SDK
- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Produces metrics and traces via OpenTelemetry SDK
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines OTel Collector service in monitoring profile
