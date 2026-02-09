# Loki Configuration

Grafana Loki 3.6.5 log aggregation backend for the rideshare simulation platform.

## Purpose

This directory contains the Loki server configuration:
- `loki-config.yaml` - Server, storage, schema, and retention settings

## Configuration

**Image**: `grafana/loki:3.6.5`
**Ports**: 3100 (HTTP API), 9096 (gRPC)
**Storage**: Filesystem (TSDB index schema v13)
**Retention**: 7 days (168h)

| Setting | Value |
|---------|-------|
| Index schema | v13 (TSDB) |
| Storage backend | filesystem (`/loki/`) |
| Ring membership | inmemory (single-node) |
| Retention period | 168h |
| Reject old samples | 168h |

## Usage

### Start Loki

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d loki
```

### Health Check

```bash
curl http://localhost:3100/ready
```

### Query Logs

```bash
curl 'http://localhost:3100/loki/api/v1/query_range?query={service_name="rideshare-simulation"}&limit=10'
```

### View Labels

```bash
curl http://localhost:3100/loki/api/v1/labels
```

### View Label Values

```bash
curl http://localhost:3100/loki/api/v1/label/service_name/values
```

## Troubleshooting

### Loki not receiving logs

Verify the OTel Collector is running and pushing to Loki:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs otel-collector
```

Check that the Loki push endpoint is reachable from the OTel Collector:

```bash
docker exec rideshare-otel-collector wget -q -O- http://loki:3100/ready
```

### Loki not ready

Check Loki logs for startup errors:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring logs loki
```

### High disk usage

Retention is set to 7 days. If disk pressure persists, prune the Docker volume:

```bash
docker volume rm rideshare-simulation-platform_loki-data
```

## References

- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/logql/)
- [Loki Configuration Reference](https://grafana.com/docs/loki/latest/configure/)
