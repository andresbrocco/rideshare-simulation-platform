# Tempo

> Distributed tracing backend (Grafana Tempo 2.10.0) that ingests OpenTelemetry traces from the OTel Collector, stores them in S3-compatible object storage, and derives Prometheus span metrics for trace-to-metrics correlation in Grafana.

## Quick Reference

### Ports

| Host Port | Container Port | Protocol | Description |
|-----------|---------------|----------|-------------|
| `3200` | `3200` | HTTP | Query API and health/ready endpoints |
| `4319` | `4317` | gRPC | OTLP trace ingestion (from OTel Collector) |

### Environment Variables

These variables are injected at runtime from the LocalStack secrets volume (`/secrets/data-pipeline.env`). They are not set in `.env` files directly.

| Variable | Source | Description |
|----------|--------|-------------|
| `MINIO_ROOT_USER` | `data-pipeline.env` | Used as `AWS_ACCESS_KEY_ID` for S3 storage backend |
| `MINIO_ROOT_PASSWORD` | `data-pipeline.env` | Used as `AWS_SECRET_ACCESS_KEY` for S3 storage backend |
| `S3_ENDPOINT` | Hardcoded in compose entrypoint | MinIO endpoint — set to `minio:9000` |
| `TEMPO_S3_BUCKET` | Hardcoded in compose entrypoint | Trace block storage bucket — set to `rideshare-tempo` |

### Health Endpoint

```
GET http://localhost:3200/ready
```

Returns HTTP 200 when Tempo is ready to ingest and serve traces. Used by Docker health check and as a dependency gate for the OTel Collector and Grafana services.

### Commands

Start Tempo (part of the `monitoring` profile):

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d tempo
```

Start the full monitoring stack:

```bash
docker compose -f infrastructure/docker/compose.yml --profile monitoring up -d
```

Tail Tempo logs:

```bash
docker compose -f infrastructure/docker/compose.yml logs -f tempo
```

### Configuration

| File | Mount Path | Description |
|------|-----------|-------------|
| `services/tempo/tempo-config.yaml` | `/etc/tempo/tempo.yaml` | Full Tempo configuration — receivers, storage, compaction, metrics generator |
| `services/tempo/Dockerfile` | — | Multi-stage build adding `wget`/`sh` from `busybox` for health checks |

Key configuration values in `tempo-config.yaml`:

| Setting | Value | Notes |
|---------|-------|-------|
| HTTP listen port | `3200` | Query API |
| OTLP gRPC endpoint | `0.0.0.0:4317` | Trace ingestion |
| WAL path | `/var/tempo/wal` | Local write-ahead log before S3 flush |
| Block retention | `1h` | Intentionally short for local dev |
| Compacted block retention | `10m` | — |
| Max block duration | `5m` | Ingester flush threshold |
| Metrics generator WAL | `/var/tempo/generator/wal` | Derived metrics storage |
| Prometheus remote-write URL | `http://prometheus:9090/api/v1/write` | Target for span metrics |
| Metrics collection interval | `5s` | How often derived metrics are pushed |

## Trace Flow

```
Application → OTel Collector (OTLP/gRPC :4317 internal)
           → Tempo (OTLP/gRPC host:4319 → container:4317)
           → WAL (/var/tempo/wal)
           → S3 blocks (MinIO: rideshare-tempo bucket)
           → Metrics Generator → Prometheus (remote-write)
           → Grafana (query via port 3200)
```

No application services send traces directly to Tempo. All traces are routed through the OTel Collector.

## Derived Metrics

The metrics generator produces three categories of Prometheus metrics from ingested traces:

| Processor | Metrics | Dimensions |
|-----------|---------|------------|
| `span-metrics` | Request rate, latency histograms, error rate per operation | `http.method`, `http.target`, `http.status_code`, `service.version` |
| `service-graphs` | Inter-service call graphs and latency | Same as above |
| `local-blocks` | TraceQL metrics for ad-hoc queries | Raw trace blocks |

All derived metrics carry labels `source=tempo`, `cluster=rideshare-simulation`, `environment=local`.

## Common Tasks

### Query a trace by ID

```bash
curl http://localhost:3200/api/traces/{trace_id}
```

### Search recent traces

```bash
curl "http://localhost:3200/api/search?limit=20&start=$(date -d '5 minutes ago' +%s)&end=$(date +%s)"
```

### List services sending traces

```bash
curl http://localhost:3200/api/services
```

### Check Tempo build info

```bash
curl http://localhost:3200/api/echo
```

### Use TraceQL to find slow spans

```bash
curl -G http://localhost:3200/api/search \
  --data-urlencode 'q={ duration > 500ms }' \
  --data-urlencode 'limit=10'
```

## Troubleshooting

**Tempo fails to start / exits immediately**

The entrypoint sources `/secrets/data-pipeline.env` to obtain MinIO credentials. If the `secrets-init` service has not completed, this file may be absent. Confirm with:

```bash
docker compose -f infrastructure/docker/compose.yml logs secrets-init
```

Tempo depends on `minio-init` completing successfully. If MinIO has not initialized the `rideshare-tempo` bucket, Tempo will error on first block flush (not on startup). Check:

```bash
docker compose -f infrastructure/docker/compose.yml logs minio-init
```

**Health check failing (`/ready` returns non-200)**

Tempo's `/ready` endpoint returns 200 only after the WAL and S3 backend are both accessible. If MinIO is unreachable or credentials are wrong, Tempo will start but remain unready. Inspect logs:

```bash
docker compose -f infrastructure/docker/compose.yml logs tempo
```

**Grafana shows no traces / "Traces Drilldown" not working**

- Confirm `stream_over_http_enabled: true` is present in `tempo-config.yaml` — this flag is required for streaming trace results to Grafana's Traces Drilldown feature.
- Confirm the Grafana Tempo datasource URL is `http://tempo:3200`.
- Confirm the OTel Collector is healthy and forwarding to `tempo:4317` internally.

**Prometheus not receiving span metrics**

Prometheus must have `--web.enable-remote-write-receiver` enabled. Without it, Tempo's metrics generator remote-write will fail silently. Check Tempo logs for `remote-write` errors. Verify the Prometheus config in `services/prometheus/` has the receiver enabled.

**S3 storage errors (forcepathstyle / insecure)**

`insecure: true` and `forcepathstyle: true` in `tempo-config.yaml` are required for MinIO/LocalStack compatibility. These flags must be removed or adjusted when deploying against real AWS S3 in production.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, non-obvious design decisions
- [services/otel-collector](../otel-collector/CONTEXT.md) — Sole trace ingestion point; routes OTLP spans to Tempo
- [services/prometheus](../prometheus/CONTEXT.md) — Remote-write target for Tempo-derived span metrics
- [services/grafana](../grafana/CONTEXT.md) — Queries Tempo for trace visualization and Traces Drilldown
- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Compose service definition and volume configuration
