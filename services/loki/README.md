# Loki

> Log aggregation service that collects structured logs from all platform services, stores them in MinIO (S3-compatible), and exposes them for Grafana queries.

## Quick Reference

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 3100 | HTTP | Loki API and push endpoint |
| 9096 | gRPC | Loki gRPC listener (internal) |

### Environment Variables

Loki is configured via `loki-config.yaml` with env var substitution (`-config.expand-env=true`). The following variables are injected at container startup from the secrets volume:

| Variable | Source | Description |
|----------|--------|-------------|
| `S3_ENDPOINT` | Hardcoded in entrypoint | MinIO address (`minio:9000`) |
| `LOKI_S3_BUCKET` | Hardcoded in entrypoint | MinIO bucket name (`rideshare-loki`) |
| `AWS_ACCESS_KEY_ID` | `data-pipeline.env` via secrets volume | MinIO root user (used as S3 access key) |
| `AWS_SECRET_ACCESS_KEY` | `data-pipeline.env` via secrets volume | MinIO root password (used as S3 secret key) |

### Configuration File

| File | Mount Path | Description |
|------|------------|-------------|
| `services/loki/loki-config.yaml` | `/etc/loki/local-config.yaml` | Loki server, storage, schema, and retention config |

Key settings in `loki-config.yaml`:

| Setting | Value | Description |
|---------|-------|-------------|
| `auth_enabled` | `false` | No multi-tenancy; single-tenant mode |
| `http_listen_port` | `3100` | HTTP API port |
| `grpc_listen_port` | `9096` | gRPC port |
| `object_store` | `s3` (MinIO) | Chunk and index storage backend |
| `schema` | `v13` (tsdb) | TSDB index with 24h period |
| `retention_period` | `168h` (7 days) | Log retention window |
| `replication_factor` | `1` | Single-node — no replication |

### Commands

Start Loki (requires `monitoring` profile):

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d loki
```

Check Loki health:

```bash
curl http://localhost:3100/ready
```

Query recent logs via LogQL:

```bash
curl -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={container="rideshare-simulation"}' \
  --data-urlencode 'start=1h' \
  --data-urlencode 'limit=50'
```

Push a test log entry:

```bash
curl -X POST http://localhost:3100/loki/api/v1/push \
  -H 'Content-Type: application/json' \
  -d '{"streams":[{"stream":{"job":"test"},"values":[["'"$(date +%s%N)"'","test log entry"]]}]}'
```

### Health Check

```bash
curl http://localhost:3100/ready
# Expected: "ready"
```

The compose healthcheck runs `/usr/bin/loki -health` every 10s (5 retries, 30s start period). Grafana and OTel Collector depend on this check passing before starting.

### Storage

| Volume | Purpose |
|--------|---------|
| `loki-data` | Compactor working directory (`/loki/compactor`) |
| MinIO bucket `rideshare-loki` | Chunk storage and TSDB index (S3 path-style) |

The `rideshare-loki` bucket is created automatically by `minio-init` before Loki starts. Loki depends on `minio-init` completing successfully.

### Docker Image

The `Dockerfile` extends `grafana/loki:3.6.5` with a BusyBox shell (`busybox:1.37-musl`) required for the entrypoint shell script that loads secrets and sets env vars before exec-ing Loki.

## Common Tasks

### View logs for a specific service

In Grafana (port 3001), open Explore, select the Loki datasource, and run:

```logql
{container="rideshare-simulation"}
```

Or via the API:

```bash
curl -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={container="rideshare-stream-processor"}' \
  --data-urlencode 'start=30m'
```

### List available log labels

```bash
curl http://localhost:3100/loki/api/v1/labels
```

### Check ingestion stats

```bash
curl http://localhost:3100/metrics | grep loki_ingester
```

### Verify MinIO connectivity

If Loki fails to start, check that MinIO is healthy and the `rideshare-loki` bucket exists:

```bash
docker compose -f infrastructure/docker/compose.yml exec minio \
  mc ls local/rideshare-loki
```

## Troubleshooting

**Loki fails healthcheck / won't start**
Loki depends on `minio-init` completing. Check `minio-init` logs first:
```bash
docker compose -f infrastructure/docker/compose.yml logs minio-init
```

**"bucket not found" or S3 errors**
The `rideshare-loki` bucket must exist in MinIO before Loki starts. Re-run `minio-init` or create it manually via the MinIO console at `http://localhost:9001`.

**No logs appearing in Grafana**
The OTel Collector (Docker log driver or OTLP) forwards logs to Loki at `http://loki:3100`. Confirm OTel Collector is running and healthy:
```bash
docker compose -f infrastructure/docker/compose.yml logs otel-collector
```

**High memory usage**
The container is memory-limited to `384m`. If Loki is OOM-killed, reduce `chunk_target_size` or increase the limit in `compose.yml`.

**Secrets not injected**
Loki reads `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` from `/secrets/data-pipeline.env`. Confirm `secrets-init` ran successfully:
```bash
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

## Related

- [services/grafana/README.md](../grafana/README.md) — Grafana dashboards that query Loki
- [services/otel-collector/README.md](../otel-collector/README.md) — OTel Collector that ships logs to Loki
- [services/tempo/README.md](../tempo/README.md) — Distributed tracing companion service
