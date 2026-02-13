# OpenTelemetry Collector

> Central telemetry pipeline routing metrics, logs, and traces from application services to observability backends (Prometheus, Loki, Tempo).

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 4317 | gRPC | OTLP receiver for metrics and traces |
| 4318 | HTTP | OTLP receiver for metrics and traces |
| 8888 | HTTP | OTel Collector self-metrics (scraped by Prometheus) |
| 13133 | HTTP | Health check endpoint |

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTLP endpoint for application services |

### Configuration Files

| File | Purpose |
|------|---------|
| `otel-collector-config.yaml` | Pipeline configuration (receivers, processors, exporters) |
| `Dockerfile` | Custom image with wget for health checks |

### Health Check

```bash
# Docker health check
curl http://localhost:13133/

# Check collector status
docker compose -f infrastructure/docker/compose.yml logs otel-collector

# Verify collector is receiving data
curl http://localhost:8888/metrics
```

### Dependencies

| Service | Purpose |
|---------|---------|
| prometheus | Metrics backend (remote write endpoint) |
| loki | Logs backend (push endpoint) |
| tempo | Traces backend (OTLP endpoint) |

## Telemetry Pipelines

### Metrics Pipeline

**Flow**: Application (OTLP) → OTel Collector → Prometheus (remote write)

**Sources**:
- `simulation` service (OpenTelemetry SDK)
- `stream-processor` service (OpenTelemetry SDK)

**Processors**:
- `memory_limiter` - Prevents OOM (180 MiB limit, 50 MiB spike)
- `batch` - Batches up to 1000 metrics every 5 seconds
- `resource` - Adds `deployment.environment=local` label

**Exporter**:
- `prometheusremotewrite` to `http://prometheus:9090/api/v1/write`

### Logs Pipeline

**Flow**: Docker container logs → OTel Collector → Loki

**Source**:
- `filelog` receiver reading `/var/lib/docker/containers/*/*.log`

**Processors**:
1. Parse Docker JSON log format
2. Extract container ID from file path
3. Parse application JSON logs (if present)
4. Extract attributes: `level`, `service`, `service_name`, `correlation_id`, `trip_id`
5. Transform `service_name` to `service.name` resource attribute
6. Add Loki label hints

**Exporter**:
- `loki` to `http://loki:3100/loki/api/v1/push`

**Loki Labels**:
- Attribute labels: `level`, `service`, `service_name`, `container_id`
- Resource labels: `service.name`, `deployment.environment`

### Traces Pipeline

**Flow**: Application (OTLP) → OTel Collector → Tempo

**Sources**:
- `simulation` service (OpenTelemetry SDK)
- `stream-processor` service (OpenTelemetry SDK)

**Processors**:
- `memory_limiter` - Prevents OOM
- `batch` - Batches traces
- `resource` - Adds environment label

**Exporter**:
- `otlp/tempo` to `tempo:4317` (insecure gRPC)

## Common Tasks

### Start OTel Collector

```bash
# Start with monitoring profile
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d otel-collector

# Verify health
curl http://localhost:13133/
```

### View Self-Metrics

```bash
# OTel Collector exposes Prometheus-format metrics about itself
curl http://localhost:8888/metrics

# Key metrics:
# - otelcol_receiver_accepted_metric_points
# - otelcol_receiver_accepted_spans
# - otelcol_exporter_sent_metric_points
# - otelcol_processor_batch_batch_send_size
```

### Test OTLP Endpoint

```bash
# Verify gRPC endpoint is reachable
grpcurl -plaintext localhost:4317 list

# Check HTTP endpoint
curl -X POST http://localhost:4318/v1/metrics \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Debug Telemetry Flow

```bash
# Enable debug exporter (edit otel-collector-config.yaml)
# Uncomment debug exporter in pipelines section

# View debug logs
docker compose -f infrastructure/docker/compose.yml logs -f otel-collector
```

### Adjust Memory Limits

```bash
# Edit otel-collector-config.yaml
# Modify memory_limiter processor:
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 256        # Increase from 180
    spike_limit_mib: 64   # Increase from 50

# Restart collector
docker compose -f infrastructure/docker/compose.yml restart otel-collector
```

## Troubleshooting

### Collector Not Starting

**Symptom**: Health check fails at startup

**Causes**:
- Invalid YAML syntax in `otel-collector-config.yaml`
- Missing dependencies (prometheus, loki, tempo)
- Port conflicts (4317, 4318, 8888, 13133)

**Solution**:
```bash
# Check logs for config errors
docker compose -f infrastructure/docker/compose.yml logs otel-collector

# Validate YAML syntax
yamllint otel-collector-config.yaml

# Check port availability
lsof -i :4317
lsof -i :4318
```

### Metrics Not Reaching Prometheus

**Symptom**: Prometheus shows no data from simulation/stream-processor

**Causes**:
- Application services not exporting OTLP metrics
- Collector not forwarding to Prometheus remote write endpoint
- Network connectivity issues

**Solution**:
```bash
# Verify collector is receiving metrics
curl http://localhost:8888/metrics | grep receiver_accepted_metric_points

# Check Prometheus remote write exporter
curl http://localhost:8888/metrics | grep exporter_sent_metric_points

# Verify application services have OTEL_EXPORTER_OTLP_ENDPOINT set
docker compose -f infrastructure/docker/compose.yml exec simulation env | grep OTEL
```

### Logs Not Reaching Loki

**Symptom**: Loki shows no container logs

**Causes**:
- Docker log directory not mounted (`/var/lib/docker/containers`)
- Loki endpoint unreachable
- Log parsing errors

**Solution**:
```bash
# Verify Docker logs volume mount
docker compose -f infrastructure/docker/compose.yml config | grep -A5 otel-collector

# Check filelog receiver status
curl http://localhost:8888/metrics | grep filelog

# Test Loki endpoint
curl http://localhost:3100/ready
```

### Traces Not Reaching Tempo

**Symptom**: Grafana shows no trace data

**Causes**:
- Tempo endpoint unreachable
- Application services not exporting spans
- OTLP exporter misconfigured

**Solution**:
```bash
# Verify collector is receiving traces
curl http://localhost:8888/metrics | grep receiver_accepted_spans

# Check Tempo OTLP exporter
curl http://localhost:8888/metrics | grep exporter_sent_spans

# Test Tempo endpoint
docker compose -f infrastructure/docker/compose.yml exec tempo wget -O- http://localhost:3200/ready
```

### Memory Limit Exceeded

**Symptom**: Collector logs show "memory limiter" warnings

**Causes**:
- High telemetry volume
- Memory limit too low (default 180 MiB)
- Batch size too large

**Solution**:
```bash
# Increase memory limit in otel-collector-config.yaml
# Reduce batch size or timeout
# Check current memory usage
docker stats otel-collector --no-stream
```

### Pipeline Not Processing Data

**Symptom**: Receiver metrics increase but exporter metrics don't

**Causes**:
- Processor errors (e.g., attribute extraction failures)
- Backend unavailable
- Configuration mismatch

**Solution**:
```bash
# Check processor metrics
curl http://localhost:8888/metrics | grep processor

# Enable debug exporter in config
# Add to exporters section: debug: { verbosity: detailed }
# Add to pipelines: exporters: [..., debug]

# Restart and view debug logs
docker compose -f infrastructure/docker/compose.yml restart otel-collector
docker compose -f infrastructure/docker/compose.yml logs -f otel-collector
```

## Application Integration

### Python (OpenTelemetry SDK)

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OTLP exporter
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Create spans
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("operation_name"):
    # Your code here
    pass
```

### Environment Variables for Applications

```bash
# Required for Python OpenTelemetry SDK
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=my-service
```

## Architecture Notes

### Collector vs. Agent Pattern

This deployment uses a single **collector** instance (not agent-per-node):
- Applications push metrics/traces via OTLP
- Docker logs are collected from mounted volume
- Suitable for Docker Compose (single host)

For Kubernetes, consider DaemonSet agent pattern for log collection.

### Processor Ordering

Processor order matters:
1. `memory_limiter` - First line of defense
2. `batch` - Reduces export calls
3. `resource` - Adds metadata
4. `attributes/*` - Extracts/transforms attributes
5. `transform/*` - Complex transformations

### Label Cardinality

Be careful with Loki labels:
- High cardinality (e.g., `trip_id`) increases memory usage
- Use structured log fields instead of labels for high-cardinality data
- Current config uses low-cardinality labels: `level`, `service`, `container_id`

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context
- [../prometheus/README.md](../prometheus/README.md) — Metrics backend
- [../loki/README.md](../loki/README.md) — Logs backend
- [../tempo/README.md](../tempo/README.md) — Traces backend
- [../grafana/README.md](../grafana/README.md) — Visualization frontend
