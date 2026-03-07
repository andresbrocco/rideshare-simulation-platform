# OTel Collector

> Central observability gateway routing metrics to Prometheus, logs to Loki, and traces to Tempo via three independent pipelines.

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 4317 | gRPC | OTLP receiver — metrics and traces ingestion |
| 4318 | HTTP | OTLP receiver — metrics and traces ingestion (HTTP alternative) |
| 8888 | HTTP | Collector self-metrics (Prometheus scrape target) |
| 13133 | HTTP | Health check endpoint (not mapped to host) |

### Configuration

| File | Purpose |
|------|---------|
| `otel-collector-config.yaml` | Full pipeline configuration — receivers, processors, exporters, extensions |

### Docker Service

```yaml
image: otel/opentelemetry-collector-contrib:0.96.0
profile: monitoring
```

Start with the monitoring profile:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d otel-collector
```

### Health Check

```bash
# Internal health endpoint (from within the Docker network)
curl http://otel-collector:13133/

# From host — check the container health status
docker inspect --format='{{.State.Health.Status}}' <container_id>
```

### Self-Metrics

```bash
# Collector's own metrics (pipeline stats, dropped spans, etc.)
curl http://localhost:8888/metrics
```

## Pipelines

Three independent pipelines process different signal types:

| Pipeline | Receiver | Batch Timeout | Exporter |
|----------|----------|---------------|---------|
| `metrics` | OTLP (gRPC/HTTP) | 1s | `prometheusremotewrite` → `http://prometheus:9090/api/v1/write` |
| `logs` | `filelog` (Docker JSON logs) | 5s | `loki` → `http://loki:3100/loki/api/v1/push` |
| `traces` | OTLP (gRPC/HTTP) | 5s | `otlp/tempo` → `tempo:4317` |

## Sending Telemetry

### From application services — metrics and traces (OTLP)

Applications configured with `OTEL_EXPORTER_OTLP_ENDPOINT` point to the collector:

```bash
# gRPC (default for most SDKs)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# HTTP
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

### Logs

Logs are collected automatically. The `filelog` receiver reads `/var/lib/docker/containers/*/*.log` directly — no per-service configuration required. Application services write to stdout/stderr; Docker captures them as JSON-wrapped files that the collector parses.

## Common Tasks

### Verify telemetry is flowing

```bash
# Check collector self-metrics for pipeline throughput
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted

# Check exporter send counts
curl -s http://localhost:8888/metrics | grep otelcol_exporter_sent
```

### Enable debug logging for troubleshooting

The `debug` exporter is defined in the config but not wired into any pipeline by default. To enable it temporarily, add it to the relevant pipeline's `exporters` list in `otel-collector-config.yaml` and restart the container:

```bash
docker compose -f infrastructure/docker/compose.yml restart otel-collector
```

### Inspect dropped data

```bash
# Check for dropped spans, metrics, or logs due to memory pressure
curl -s http://localhost:8888/metrics | grep otelcol_processor_dropped
```

### Tail collector logs

```bash
docker compose -f infrastructure/docker/compose.yml logs -f otel-collector
```

## Troubleshooting

**Collector exits with OOM**: The `memory_limiter` processor caps usage at 180 MiB (spike limit: 50 MiB). If upstream services burst too much telemetry, the collector drops data rather than OOM. Reduce `send_batch_size` or increase `limit_mib` in `otel-collector-config.yaml`.

**Logs not appearing in Loki**: The `filelog` receiver requires the Docker socket directory (`/var/lib/docker/containers`) to be volume-mounted into the container. Verify the compose volume mount is present. Also confirm that the service writes JSON-formatted logs — the `app_log_parser` only activates when the `log` field starts with `{`.

**Metrics not reaching Prometheus**: Metrics use `prometheusremotewrite` (push), not a scrape endpoint. Verify Prometheus has `--web.enable-remote-write-receiver` enabled and check `otelcol_exporter_send_failed_metric_points` in the collector's self-metrics.

**Traces not in Tempo**: Confirm the sending service sets `OTEL_EXPORTER_OTLP_ENDPOINT` to point at the collector (not directly at Tempo). Check `otelcol_exporter_sent_spans` to see if spans are leaving the collector.

**Health check failing**: The Dockerfile copies `wget` from BusyBox into the OTel image because the `otel/opentelemetry-collector-contrib` image has no wget binary by default. If the image is rebuilt without this layer, Docker health checks will fail silently.

**Loki label cardinality**: Only `level`, `service`, `service_name`, and `container_id` are promoted to indexed Loki labels. Other log attributes (e.g., `correlation_id`, `trip_id`) are stored as unindexed metadata and cannot be used in label matchers — use `|= "correlation_id=..."` log line filters instead.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: pipeline design, log parsing strategy, label promotion
- [services/prometheus/README.md](../prometheus/README.md) — Metric storage backend
- [services/tempo/README.md](../tempo/README.md) — Trace storage backend
- [services/loki/README.md](../loki/README.md) — Log storage backend
