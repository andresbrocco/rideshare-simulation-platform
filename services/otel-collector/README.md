# OpenTelemetry Collector Configuration

OpenTelemetry Collector Contrib 0.96.0 unified telemetry pipeline for the rideshare simulation platform.

## Purpose

This directory contains the OTel Collector configuration and custom Docker image:
- `otel-collector-config.yaml` - Receivers, processors, exporters, and pipeline definitions
- `Dockerfile` - Custom image that adds wget for health checks

## Configuration

**Image**: `otel/opentelemetry-collector-contrib:0.96.0` (custom Dockerfile)
**Ports**: 4317 (OTLP gRPC), 4318 (OTLP HTTP), 8888 (collector metrics), 13133 (health check)
**User**: root (`0:0`) for Docker socket and log file access

| Port | Protocol | Purpose |
|------|----------|---------|
| 4317 | gRPC | OTLP receiver (traces + metrics from apps) |
| 4318 | HTTP | OTLP receiver (traces + metrics from apps) |
| 8888 | HTTP | Collector self-metrics |
| 13133 | HTTP | Health check extension |

## Pipelines

| Pipeline | Receiver | Exporter | Data Flow |
|----------|----------|----------|-----------|
| metrics | OTLP (gRPC/HTTP) | Prometheus remote write | Apps → Collector → Prometheus |
| logs | filelog (Docker JSON) | Loki push API | Container logs → Collector → Loki |
| traces | OTLP (gRPC/HTTP) | OTLP gRPC | Apps → Collector → Tempo |

## Usage

### Build Image

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring build otel-collector
```

### Start OTel Collector

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d otel-collector
```

### Health Check

```bash
curl http://localhost:13133/
```

### View Collector Metrics

```bash
curl http://localhost:8888/metrics
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs -f otel-collector
```

## Troubleshooting

### Collector not starting

Check that Docker socket is accessible and container logs directory exists:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs otel-collector
```

### Logs not appearing in Loki

Verify the filelog receiver is reading container logs:

```bash
# Check collector metrics for filelog receiver stats
curl -s http://localhost:8888/metrics | grep filelog
```

Verify Loki is reachable:

```bash
docker exec rideshare-otel-collector wget -q -O- http://loki:3100/ready
```

### Traces not appearing in Tempo

Verify Tempo is reachable from the collector:

```bash
docker exec rideshare-otel-collector wget -q -O- http://tempo:3200/ready
```

### Health check failing

The health check uses `wget` (added via the custom Dockerfile). If the image was not built properly:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring build --no-cache otel-collector
```

## References

- [OpenTelemetry Collector Documentation](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [Filelog Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/filelogreceiver)
- [Loki Exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/lokiexporter)
