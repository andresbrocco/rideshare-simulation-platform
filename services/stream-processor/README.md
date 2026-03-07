# Stream Processor

> Kafka-to-Redis bridge that consumes simulation events, applies windowed GPS aggregation, deduplicates via Redis SET NX, and publishes results to Redis pub/sub for the frontend WebSocket layer.

## Quick Reference

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 8080 | HTTP | Health check and metrics API |

### Environment Variables

#### Kafka

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Yes | Comma-separated broker addresses |
| `KAFKA_SASL_USERNAME` | — | **Yes** | SASL username (required even for PLAINTEXT; use dummy value locally) |
| `KAFKA_SASL_PASSWORD` | — | **Yes** | SASL password (required even for PLAINTEXT; use dummy value locally) |
| `KAFKA_CONSUMER_GROUP_ID` | `stream-processor` | No | Consumer group ID |
| `KAFKA_SESSION_TIMEOUT_MS` | `30000` | No | Consumer session timeout in ms |
| `KAFKA_MAX_POLL_INTERVAL_MS` | `300000` | No | Max time between polls before rebalance |

#### Redis

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REDIS_HOST` | `localhost` | Yes | Redis hostname |
| `REDIS_PORT` | `6379` | No | Redis port |
| `REDIS_PASSWORD` | — | **Yes** | Redis password (validated at startup) |
| `REDIS_DB` | `0` | No | Redis database index |

#### Processor Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | GPS aggregation window duration (50–5000 ms) |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | GPS reduction strategy: `latest` or `sample` |
| `PROCESSOR_BATCH_SIZE` | `100` | Kafka offset commit batch size |
| `PROCESSOR_FLUSH_INTERVAL` | `5` | Time-based offset commit interval in seconds |
| `PROCESSOR_GPS_ENABLED` | `true` | Toggle GPS handler |
| `PROCESSOR_TRIPS_ENABLED` | `true` | Toggle trip events handler |
| `PROCESSOR_DRIVER_STATUS_ENABLED` | `true` | Toggle driver status handler |
| `PROCESSOR_SURGE_ENABLED` | `true` | Toggle surge pricing handler |

#### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OpenTelemetry Collector endpoint for traces and metrics |
| `OTEL_SERVICE_NAME` | — | Service name reported to OTLP |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SCHEMA_REGISTRY_URL` | — | Confluent Schema Registry URL |
| `DEPLOYMENT_ENV` | — | Runtime environment label (`local`, `production`) |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness and connection status |
| `GET` | `/metrics` | Throughput, latency, and GPS aggregation stats |

**Health check:**

```bash
curl http://localhost:8080/health
```

Example response:

```json
{
  "status": "healthy",
  "kafka_connected": true,
  "redis_connected": true,
  "uptime_seconds": 142.3,
  "message": "All connections active"
}
```

Status values: `healthy` (both connections active), `degraded` (one connection lost), `unhealthy` (all connections lost).

**Metrics snapshot:**

```bash
curl http://localhost:8080/metrics
```

Example response:

```json
{
  "messages_consumed_total": 48201,
  "messages_published_total": 9640,
  "messages_consumed_per_sec": 312.4,
  "messages_published_per_sec": 62.5,
  "gps_aggregation_ratio": 5.0,
  "redis_publish_latency": {"avg_ms": 1.2, "p95_ms": 3.8, "count": 9640},
  "publish_errors": 0,
  "publish_errors_per_sec": 0.0,
  "kafka_connected": true,
  "redis_connected": true,
  "uptime_seconds": 142.3,
  "timestamp": 1741394965.0
}
```

### Kafka Topics Consumed

| Topic | Handler | Windowed | Always Enabled |
|-------|---------|----------|----------------|
| `gps_pings` | GPSHandler | Yes (window = `PROCESSOR_WINDOW_SIZE_MS`) | No — toggle with `PROCESSOR_GPS_ENABLED` |
| `trips` | TripHandler | No | No — toggle with `PROCESSOR_TRIPS_ENABLED` |
| `driver_status` | DriverStatusHandler | No | No — toggle with `PROCESSOR_DRIVER_STATUS_ENABLED` |
| `surge_updates` | SurgeHandler | No | No — toggle with `PROCESSOR_SURGE_ENABLED` |
| `driver_profiles` | DriverProfileHandler | No | **Yes** |
| `rider_profiles` | RiderProfileHandler | No | **Yes** |
| `ratings` | RatingHandler | No | **Yes** |

### Redis Pub/Sub Channels

Events are published to Redis pub/sub channels consumed by the simulation service WebSocket layer. Deduplication keys are stored as `event:processed:<event_id>` with a 1-hour TTL using `SET NX EX`.

### Prometheus Metrics (via OTLP)

| Metric | Type | Description |
|--------|------|-------------|
| `stream_processor_messages_consumed_total` | Counter | Total messages consumed from Kafka |
| `stream_processor_messages_published_total` | Counter | Total messages published to Redis |
| `stream_processor_gps_received_total` | Counter | Total GPS pings received |
| `stream_processor_gps_emitted_total` | Counter | Total aggregated GPS updates emitted |
| `stream_processor_publish_errors_total` | Counter | Total Redis publish errors |
| `stream_processor_validation_errors_total` | Counter | Validation errors labelled by `handler_type` |
| `stream_processor_gps_aggregation_ratio` | Observable Gauge | Ratio of GPS pings received to updates emitted |
| `stream_processor_kafka_connected` | Observable Gauge | `1` = connected, `0` = disconnected |
| `stream_processor_redis_connected` | Observable Gauge | `1` = connected, `0` = disconnected |
| `stream_processor_uptime_seconds` | Observable Gauge | Service uptime |
| `stream_processor_redis_publish_latency_seconds` | Histogram | Redis publish latency |
| `stream_processor_pipeline_latency_seconds` | Histogram | End-to-end latency from Kafka produce to Redis publish |

### Prerequisites

- Kafka broker reachable at `KAFKA_BOOTSTRAP_SERVERS`
- Redis instance reachable at `REDIS_HOST:REDIS_PORT` with password set
- `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD` must be non-empty (even for PLAINTEXT security protocol)
- `REDIS_PASSWORD` must be non-empty — both are validated by Pydantic at startup

## Common Tasks

### Check if the processor is keeping up with Kafka

```bash
# Compare consumed vs published rates — a large gap signals backpressure or errors
curl -s http://localhost:8080/metrics | python3 -m json.tool | grep per_sec
```

### Measure GPS aggregation efficiency

```bash
# gps_aggregation_ratio shows how many raw pings collapse into one emitted update
curl -s http://localhost:8080/metrics | python3 -m json.tool | grep aggregation
```

### Adjust GPS window size without rebuilding

Set `PROCESSOR_WINDOW_SIZE_MS` in the environment and restart the container. Valid range is 50–5000 ms. Larger windows reduce Redis traffic but increase frontend update latency.

### Disable a handler for debugging

Set the relevant env var to `false` and restart:

```bash
PROCESSOR_GPS_ENABLED=false
PROCESSOR_SURGE_ENABLED=false
```

Note: `driver_profiles`, `rider_profiles`, and `ratings` handlers cannot be disabled.

### Run the stream processor locally (Docker)

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up stream-processor
```

### Run tests

```bash
cd services/stream-processor && ./venv/bin/pytest
```

### Type-check

```bash
cd services/stream-processor && ./venv/bin/mypy src/
```

## Troubleshooting

**Startup fails with "Required credentials not provided: KAFKA_SASL_USERNAME"**

`KafkaSettings` validates that both `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD` are non-empty regardless of `security.protocol`. In local development, set them to any non-empty dummy values.

**Consumer hangs after startup with no messages processed**

The processor waits up to 30 seconds for partition assignment before proceeding. If topics (`gps_pings`, `trips`, etc.) do not exist yet, the consumer will log `"Topics not available yet"` and retry. This is expected — the simulation creates topics on its first event publish.

**Health endpoint returns `degraded` or `unhealthy`**

- `kafka_connected: false` — the consumer's poll loop has not started or has exited. Check logs for Kafka errors.
- `redis_connected: false` — `RedisSink.ping()` failed. Verify `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD`.

**High `publish_errors` count**

Redis connection failures during `publish_batch`. The sink uses exponential backoff retries (up to `PROCESSOR_MAX_RETRIES`, default 3). Persistent errors indicate Redis is unreachable or the password changed.

**GPS aggregation ratio is 1.0 (no reduction)**

Either `PROCESSOR_WINDOW_SIZE_MS` is too small for the simulation's GPS emit rate, or `PROCESSOR_AGGREGATION_STRATEGY=sample` with `PROCESSOR_SAMPLE_RATE=1`. Increase window size or sample rate.

**`stream_processor_validation_errors_total` appears in Prometheus**

This counter only appears after the first validation error. Zero on a healthy system means no errors have occurred — this is expected and not a misconfiguration.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: two-thread model, deduplication internals, non-obvious gotchas
- [services/simulation/src/api](../simulation/src/api/README.md) — Upstream producer writing to Kafka topics consumed here
- [services/grafana/dashboards/monitoring](../grafana/dashboards/monitoring/CONTEXT.md) — Grafana dashboard consuming these Prometheus metrics
- [services/prometheus/rules](../prometheus/rules/CONTEXT.md) — Alerting rules referencing stream-processor metrics
