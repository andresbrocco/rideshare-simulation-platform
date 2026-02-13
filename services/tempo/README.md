# Tempo

> Distributed tracing backend for storing and querying traces from the rideshare simulation platform

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 3200 | HTTP | Tempo API (health, query, metrics) |
| 4319 | gRPC | OTLP trace ingestion (mapped from internal 4317) |

### Configuration Files

| File | Purpose |
|------|---------|
| `tempo-config.yaml` | Main Tempo configuration (receivers, storage, metrics generator) |
| `Dockerfile` | Custom image with wget for health checks |

### Health Check

```bash
# Check Tempo health
curl http://localhost:3200/ready

# Expected response: HTTP 200
```

### Docker Profile

This service is part of the `monitoring` profile:

```bash
# Start Tempo with other monitoring services
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d

# View Tempo logs
docker compose -f infrastructure/docker/compose.yml logs -f tempo

# Check Tempo health from inside compose network
docker compose -f infrastructure/docker/compose.yml exec tempo wget --no-verbose --tries=1 --spider http://localhost:3200/ready
```

## Architecture

### Trace Flow

```
Application Services (OpenTelemetry SDK)
  ↓
OTel Collector (OTLP exporter)
  ↓ OTLP gRPC (port 4319)
Tempo (distributor → ingester → compactor)
  ↓ Remote Write
Prometheus (span metrics + service graphs)
  ↓ Query
Grafana (TraceQL, Traces Drilldown)
```

### Storage

**Local Storage Mode** (single-node, no external object store):

- WAL: `/var/tempo/wal` — Write-ahead log for incoming traces
- Blocks: `/var/tempo/blocks` — Compacted trace blocks
- Generator WAL: `/var/tempo/generator/wal` — Metrics generator storage
- Generator Traces: `/var/tempo/generator/traces` — Trace metadata for metrics

**Retention:**
- Block retention: 1 hour
- Compacted block retention: 10 minutes

### Metrics Generator

Tempo generates two types of metrics from ingested traces:

1. **Span Metrics** — Histograms and counters of trace spans
   - Dimensions: `http.method`, `http.target`, `http.status_code`, `service.version`
2. **Service Graphs** — Inter-service relationship metrics for dependency visualization
   - Dimensions: Same as span metrics

Both are pushed to Prometheus via remote write (`http://prometheus:9090/api/v1/write`).

**Labels applied to generated metrics:**
```yaml
source: tempo
cluster: rideshare-simulation
environment: local
```

### Stream Over HTTP

`stream_over_http_enabled: true` enables streaming trace results to Grafana, required for the **Traces Drilldown** feature.

## Common Tasks

### Query Traces in Grafana

1. Open Grafana at http://localhost:3001 (admin/admin)
2. Navigate to **Explore** → Select **Tempo** datasource
3. Use **TraceQL** to query traces:

```traceql
# Find traces for the simulation service with errors
{ service.name="simulation" && status=error }

# Find slow traces (>1s duration)
{ duration > 1s }

# Find traces by HTTP endpoint
{ http.target="/api/simulation/start" }

# Complex query: slow trips endpoint calls
{ service.name="simulation" && http.target=~"/trips.*" && duration > 500ms }
```

### View Span Metrics in Prometheus

Tempo pushes derived metrics to Prometheus. Query them at http://localhost:9090:

```promql
# Request rate by service
rate(traces_spanmetrics_calls_total[5m])

# Latency percentiles
histogram_quantile(0.95, traces_spanmetrics_latency_bucket)

# Error rate
rate(traces_spanmetrics_calls_total{status_code=~"5.."}[5m])
```

### Verify Trace Ingestion

```bash
# Check Tempo is receiving traces
curl http://localhost:3200/api/status/services

# Check metrics generator status
docker compose -f infrastructure/docker/compose.yml logs tempo | grep "metrics_generator"

# Verify remote write to Prometheus
docker compose -f infrastructure/docker/compose.yml logs tempo | grep "remote_write"
```

### Inspect Configuration

```bash
# View active configuration
docker compose -f infrastructure/docker/compose.yml exec tempo cat /etc/tempo.yaml

# Check storage paths
docker compose -f infrastructure/docker/compose.yml exec tempo ls -lh /var/tempo/wal
docker compose -f infrastructure/docker/compose.yml exec tempo ls -lh /var/tempo/blocks
```

## Troubleshooting

### Traces Not Appearing in Grafana

**Symptoms:** Grafana shows "No traces found" when querying Tempo.

**Checks:**

1. Verify OTel Collector is forwarding traces to Tempo:
   ```bash
   docker compose -f infrastructure/docker/compose.yml logs otel-collector | grep tempo
   ```

2. Check Tempo is receiving traces on port 4317:
   ```bash
   docker compose -f infrastructure/docker/compose.yml logs tempo | grep "distributor"
   ```

3. Verify Tempo health:
   ```bash
   curl http://localhost:3200/ready
   curl http://localhost:3200/api/status/buildinfo
   ```

4. Check Grafana datasource configuration:
   - URL should be `http://tempo:3200`
   - No authentication required

### Remote Write Errors to Prometheus

**Symptoms:** Logs show `remote_write: error pushing metrics to Prometheus`.

**Cause:** Prometheus service not running or unreachable.

**Solution:**

1. Verify Prometheus is running:
   ```bash
   curl http://localhost:9090/-/healthy
   ```

2. Check Docker network connectivity:
   ```bash
   docker compose -f infrastructure/docker/compose.yml exec tempo ping prometheus
   ```

3. Restart Tempo to retry connection:
   ```bash
   docker compose -f infrastructure/docker/compose.yml restart tempo
   ```

**Note:** Tempo will continue storing traces even if remote write fails. Only span metrics generation is affected.

### High Memory Usage

**Symptoms:** Tempo container using excessive memory.

**Causes:**
- Large trace volume with short compaction window
- Metrics generator accumulating too many metrics

**Tuning:**

Edit `tempo-config.yaml`:

```yaml
# Reduce ingester max block size
ingester:
  max_block_bytes: 500_000  # Default: 1_000_000

# Increase compaction window
compactor:
  compaction:
    compaction_window: 2h  # Default: 1h

# Reduce metrics collection interval
metrics_generator:
  registry:
    collection_interval: 10s  # Default: 5s
```

Then restart Tempo:
```bash
docker compose -f infrastructure/docker/compose.yml restart tempo
```

### Port Conflict on 4317

**Why 4319?** The OTel Collector already uses port 4317 for its own OTLP gRPC receiver. Tempo's receiver is mapped to 4319 on the host to avoid conflict.

**Internal communication:** Within Docker Compose network, OTel Collector sends traces to `tempo:4317` (internal port).

## Integration Points

### Receives Traces From

- **OTel Collector** (`otel-collector:4317` → `tempo:4317`) via OTLP gRPC

### Sends Metrics To

- **Prometheus** (`prometheus:9090/api/v1/write`) via remote write

### Queried By

- **Grafana** (`tempo:3200`) for trace visualization and TraceQL queries

## Related Documentation

- [CONTEXT.md](CONTEXT.md) — Architecture details for Tempo configuration
- [services/otel-collector/](../otel-collector/) — Trace collection and forwarding
- [services/prometheus/](../prometheus/) — Span metrics storage
- [services/grafana/](../grafana/) — Trace visualization
- [docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) — Monitoring stack overview
