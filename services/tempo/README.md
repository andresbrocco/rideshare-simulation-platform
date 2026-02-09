# Tempo Configuration

Grafana Tempo 2.10.0 distributed tracing backend for the rideshare simulation platform.

## Purpose

This directory contains the Tempo server configuration and custom Docker image:
- `tempo-config.yaml` - Server, storage, metrics generator, and query settings
- `Dockerfile` - Custom image that adds wget for health checks

## Configuration

**Image**: `grafana/tempo:2.10.0` (custom Dockerfile)
**Ports**: 3200 (HTTP query API), 4319→4317 (OTLP gRPC ingestion)
**Storage**: Local filesystem (`/var/tempo`)

| Setting | Value |
|---------|-------|
| Trace ingestion | OTLP gRPC (port 4317) |
| Query API | HTTP (port 3200) |
| WAL path | `/var/tempo/wal` |
| Block storage | `/var/tempo/blocks` |
| Metrics generator | span-metrics, service-graphs |
| Remote write target | `http://prometheus:9090/api/v1/write` |
| Stream over HTTP | enabled |

## Usage

### Build Image

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring build tempo
```

### Start Tempo

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d tempo
```

### Health Check

```bash
curl http://localhost:3200/ready
```

### Query a Trace by ID

```bash
curl http://localhost:3200/api/traces/<trace-id>
```

### Search Traces

```bash
curl 'http://localhost:3200/api/search?q={span.http.status_code=500}&limit=10'
```

## Troubleshooting

### Tempo not receiving traces

Verify the OTel Collector is running and forwarding traces:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs otel-collector
```

Check that the OTLP gRPC endpoint is reachable:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs tempo
```

### Health check failing

The health check uses `wget` (added via the custom Dockerfile). If the image was not built properly:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring build --no-cache tempo
```

### Metrics generator remote write errors

Tempo logs remote write errors if Prometheus is not running. Start Prometheus first:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d prometheus
```

## References

- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/latest/)
- [TraceQL Query Language](https://grafana.com/docs/tempo/latest/traceql/)
- [Tempo Configuration Reference](https://grafana.com/docs/tempo/latest/configuration/)
- [Tempo Metrics Generator](https://grafana.com/docs/tempo/latest/metrics-generator/)
