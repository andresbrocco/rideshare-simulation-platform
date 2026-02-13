# Loki

> Log aggregation backend for the rideshare simulation platform's observability stack

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 3100 | HTTP | LogQL API, log ingestion endpoint |
| 9096 | gRPC | Internal gRPC server (not exposed) |

### Configuration

| File | Purpose |
|------|---------|
| `loki-config.yaml` | Loki server configuration (storage, retention, indexing) |

### Docker Service

```bash
# Start Loki (part of monitoring profile)
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d loki

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f loki

# Check health
docker compose -f infrastructure/docker/compose.yml exec loki /usr/bin/loki -health

# Stop Loki
docker compose -f infrastructure/docker/compose.yml stop loki
```

**Image**: `grafana/loki:3.6.5`
**Container Name**: `rideshare-loki`
**Memory Limit**: 384m
**Health Check**: `/usr/bin/loki -health`

## Key Settings

### Storage

- **Storage Type**: Filesystem (single-node mode)
- **Data Location**: `/loki` (mounted as Docker volume `loki-data`)
- **Chunks Directory**: `/loki/chunks`
- **Rules Directory**: `/loki/rules`
- **Compactor Directory**: `/loki/compactor`

### Indexing

- **Schema Version**: TSDB v13 (latest recommended schema)
- **Index Prefix**: `index_`
- **Index Period**: 24h
- **Store**: `tsdb`
- **Object Store**: `filesystem`

### Retention

- **Retention Period**: 168h (7 days)
- **Retention Enforcement**: Compactor-based deletion
- **Volume Enabled**: `true`

### Authentication

- **Auth Enabled**: `false` (no authentication required)

## API Endpoints

### Log Ingestion

```bash
# Push logs (used by OTel Collector)
curl -X POST http://localhost:3100/loki/api/v1/push \
  -H "Content-Type: application/json" \
  -d '{
    "streams": [
      {
        "stream": {"service_name": "simulation", "level": "info"},
        "values": [["1234567890000000000", "Log message here"]]
      }
    ]
  }'
```

### LogQL Queries

```bash
# Query logs
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={service_name="simulation"}' \
  --data-urlencode 'start=1h' \
  --data-urlencode 'limit=100'

# Get labels
curl http://localhost:3100/loki/api/v1/labels

# Get label values
curl http://localhost:3100/loki/api/v1/label/service_name/values
```

### Health & Metrics

```bash
# Health check
curl http://localhost:3100/ready

# Metrics (Prometheus format)
curl http://localhost:3100/metrics

# Build info
curl http://localhost:3100/loki/api/v1/status/buildinfo
```

## Common Tasks

### Query Logs in Grafana

1. Navigate to Grafana: http://localhost:3001 (admin/admin)
2. Go to Explore
3. Select "Loki" datasource
4. Use LogQL queries:
   ```
   {service_name="simulation"} |= "error"
   {level="error"} | json
   {container_id="rideshare-simulation"} | pattern `<_> <level> <msg>`
   ```

### Check Log Volume by Service

```bash
# Query log volume metrics
curl -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query=sum by (service_name) (count_over_time({service_name=~".+"}[1m]))' \
  --data-urlencode 'start=1h'
```

### Verify Retention Policy

```bash
# Check compactor metrics for deletion operations
curl http://localhost:3100/metrics | grep loki_compactor

# Expected: loki_compactor_marked_chunks_total increases as old chunks are deleted
```

### Inspect Storage

```bash
# Access container
docker compose -f infrastructure/docker/compose.yml exec loki sh

# Check storage directories
ls -lh /loki/chunks
ls -lh /loki/compactor
du -sh /loki/*
```

## Integration Points

### Upstream (Log Producers)

**OpenTelemetry Collector** (`otel-collector:4318`)
- Collects logs from Docker containers via filelog receiver
- Enriches logs with labels (service_name, level, container_id)
- Pushes to Loki at `http://loki:3100/loki/api/v1/push`
- See: `services/otel-collector/otel-collector-config.yaml`

### Downstream (Log Consumers)

**Grafana** (`grafana:3000`)
- Queries Loki via LogQL
- Datasource: `http://loki:3100`
- See: `services/grafana/provisioning/datasources/datasources.yml`

## Troubleshooting

### No Logs Appearing

**Check OTel Collector is running and healthy:**
```bash
docker compose -f infrastructure/docker/compose.yml ps otel-collector
docker compose -f infrastructure/docker/compose.yml logs otel-collector | grep loki
```

**Verify Loki is receiving logs:**
```bash
curl http://localhost:3100/metrics | grep loki_distributor_lines_received_total
# Should show increasing counter
```

**Check for ingestion errors:**
```bash
curl http://localhost:3100/metrics | grep loki_discarded
```

### High Memory Usage

**Check ingestion rate:**
```bash
curl http://localhost:3100/metrics | grep loki_ingester_streams_created_total
curl http://localhost:3100/metrics | grep loki_ingester_chunks_created_total
```

**Reduce label cardinality:**
- Review OTel Collector configuration for `loki.attribute.labels`
- Avoid high-cardinality attributes like request IDs, user IDs as labels
- Use structured log parsing instead (JSON, pattern extractors)

### Retention Not Working

**Verify compactor is running:**
```bash
docker compose -f infrastructure/docker/compose.yml logs loki | grep compactor
```

**Check retention configuration:**
```bash
docker compose -f infrastructure/docker/compose.yml exec loki cat /etc/loki/local-config.yaml | grep retention
```

**Expected:**
- `retention_period: 168h`
- `retention_enabled: true`
- `volume_enabled: true`

### Query Performance Issues

**Limit query time range:**
```bash
# Bad: unbounded query
{service_name="simulation"}

# Good: time-bounded query
{service_name="simulation"} [1h]
```

**Use label filters before line filters:**
```bash
# Less efficient
{service_name=~".+"} |= "error"

# More efficient
{service_name="simulation", level="error"}
```

**Check query metrics:**
```bash
curl http://localhost:3100/metrics | grep loki_query
```

## Architecture Notes

**Single-Node Deployment**: Loki runs in monolithic mode with all components (distributor, ingester, querier, compactor) in a single process. The ring uses `inmemory` kvstore with `replication_factor: 1`. Not suitable for production HA deployments.

**Push-Based Model**: Unlike Prometheus (pull), Loki requires log shippers (OTel Collector) to push logs. Applications do not send logs directly to Loki.

**Label-Oriented Indexing**: Loki indexes labels, not log content. Full-text search is performed at query time using log line filters (`|=`, `|~`). Keep label cardinality low (<100 unique label combinations per stream).

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, schema details, retention enforcement
- [OpenTelemetry Collector](../otel-collector/README.md) — Log collection and forwarding
- [Grafana](../grafana/README.md) — Log visualization and exploration
- [Tempo](../tempo/README.md) — Distributed tracing backend (companion service)
