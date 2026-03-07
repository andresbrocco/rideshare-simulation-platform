# Bronze Ingestion

> Kafka-to-Bronze Delta Lake ingestion service — consumes all simulation event topics and persists raw JSON records to partitioned Delta tables on S3/MinIO.

## Quick Reference

### Ports

| Port (Host) | Port (Container) | Description |
|-------------|-----------------|-------------|
| 8086 | 8080 | Health endpoint |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka broker address |
| `KAFKA_CONSUMER_GROUP` | `bronze-ingestion` | Consumer group ID |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | Security protocol (`PLAINTEXT`, `SASL_PLAINTEXT`, `SASL_SSL`) |
| `KAFKA_SASL_MECHANISM` | `PLAIN` | SASL mechanism when not using PLAINTEXT |
| `KAFKA_SASL_USERNAME` | _(empty)_ | SASL username |
| `KAFKA_SASL_PASSWORD` | _(empty)_ | SASL password |
| `DELTA_BASE_PATH` | `s3a://rideshare-bronze` | Base path for Delta tables (supports `s3://`, `s3a://`, local paths) |
| `BRONZE_BUCKET` | `rideshare-bronze` | S3/MinIO bucket name |
| `BATCH_INTERVAL_SECONDS` | `10` | Flush interval — how often accumulated messages are written to Delta |
| `KAFKA_POLL_TIMEOUT_MS` | `1000` | Kafka poll timeout in milliseconds |
| `S3_ENDPOINT_URL` | _(empty)_ | S3-compatible endpoint (set to MinIO URL in local dev) |
| `S3_ENDPOINT` | _(empty)_ | Alternate env var for S3 endpoint (fallback if `S3_ENDPOINT_URL` is empty) |
| `AWS_ACCESS_KEY_ID` | _(empty)_ | AWS/MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | _(empty)_ | AWS/MinIO secret key |
| `AWS_REGION` | `us-east-1` | AWS region |
| `DLQ_ENABLED` | `true` | Enable Dead Letter Queue routing for invalid messages |
| `DLQ_VALIDATE_JSON` | `false` | Validate message JSON structure before routing to DLQ |
| `DLQ_VALIDATE_SCHEMA` | `false` | Validate messages against JSON Schema files |
| `DLQ_SCHEMA_DIR` | `/app/schemas` | Directory containing JSON Schema files for validation |

### Health Endpoint

| Method | Path | Port | Description |
|--------|------|------|-------------|
| `GET` | `/health` | 8086 (host) / 8080 (container) | Returns service health and write statistics |

**Healthy response (HTTP 200):**
```json
{
  "status": "healthy",
  "last_write": "2024-01-15T10:30:00+00:00",
  "messages_written": 42150,
  "dlq_messages": 3,
  "errors": 0
}
```

**Unhealthy response (HTTP 503):**
```json
{
  "status": "unhealthy",
  "last_write": "2024-01-15T10:29:45+00:00",
  "messages_written": 42150,
  "dlq_messages": 3,
  "errors": 2
}
```

The error counter resets to zero after any successful batch write, allowing recovery from transient S3 errors without a restart.

### Subscribed Kafka Topics

The service subscribes to all 8 simulation event topics:

| Topic | Bronze Table | DLQ Table |
|-------|-------------|-----------|
| `gps_pings` | `bronze_gps_pings` | `dlq_bronze_gps_pings` |
| `trips` | `bronze_trips` | `dlq_bronze_trips` |
| `driver_status` | `bronze_driver_status` | `dlq_bronze_driver_status` |
| `surge_updates` | `bronze_surge_updates` | `dlq_bronze_surge_updates` |
| `ratings` | `bronze_ratings` | `dlq_bronze_ratings` |
| `payments` | `bronze_payments` | `dlq_bronze_payments` |
| `driver_profiles` | `bronze_driver_profiles` | `dlq_bronze_driver_profiles` |
| `rider_profiles` | `bronze_rider_profiles` | `dlq_bronze_rider_profiles` |

### Bronze Delta Table Schema

All topics share an identical schema — no event-specific fields are extracted at this layer:

| Column | Type | Description |
|--------|------|-------------|
| `_raw_value` | `string` | Raw UTF-8 JSON payload from Kafka |
| `_kafka_partition` | `int32` | Kafka partition number |
| `_kafka_offset` | `int64` | Kafka message offset |
| `_kafka_timestamp` | `timestamp(us, UTC)` | Kafka message timestamp |
| `_ingested_at` | `timestamp(us, UTC)` | Time the record was written to Delta |
| `_ingestion_date` | `string` | Partition column — `YYYY-MM-DD` format |

Tables are partitioned by `_ingestion_date`.

### Docker Service

| Property | Value |
|----------|-------|
| Profile | `data-pipeline` |
| Image | Custom build (see `Dockerfile`) |
| Runtime | Python 3.12 |
| Health check | `curl -f http://localhost:8080/health` (30s interval, 5s timeout, 3 retries) |

### Configuration File

`services/bronze-ingestion/src/config.py` — `BronzeIngestionConfig` and `DLQConfig` dataclasses built from environment variables via `from_env()`.

## Common Tasks

### Check service health

```bash
curl http://localhost:8086/health
```

### Start with the data-pipeline profile

```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up bronze-ingestion -d
```

### View live logs

```bash
docker compose -f infrastructure/docker/compose.yml logs -f bronze-ingestion
```

### Check how many messages have been written

```bash
curl -s http://localhost:8086/health | python3 -m json.tool
```

### Query a Bronze table via Trino

```sql
-- Count raw records by ingestion date
SELECT _ingestion_date, COUNT(*) AS record_count
FROM bronze.bronze_gps_pings
GROUP BY _ingestion_date
ORDER BY _ingestion_date DESC;
```

### Inspect DLQ records for a topic

```sql
-- Find all DLQ records and their error types
SELECT error_type, error_message, kafka_topic, _kafka_offset
FROM bronze.dlq_bronze_gps_pings
ORDER BY _ingested_at DESC
LIMIT 50;
```

### Enable JSON schema validation

Set these environment variables to validate message structure against JSON Schema files mounted at `DLQ_SCHEMA_DIR`:

```bash
DLQ_VALIDATE_JSON=true
DLQ_VALIDATE_SCHEMA=true
DLQ_SCHEMA_DIR=/app/schemas
```

Topics without a matching schema file silently pass through validation — no error is raised for a missing schema file.

### Tune batch flush frequency

Reduce `BATCH_INTERVAL_SECONDS` to flush more frequently (lower latency, more S3 writes). Increase it to reduce S3 API calls (higher latency, larger batches):

```bash
BATCH_INTERVAL_SECONDS=30   # flush every 30 seconds
```

## Troubleshooting

### Health endpoint returns 503

The service has encountered consecutive Delta write errors. Check logs for S3/MinIO connectivity issues:

```bash
docker compose -f infrastructure/docker/compose.yml logs bronze-ingestion | grep -i error
```

The error counter resets automatically on the next successful batch write — no restart needed if the underlying issue (e.g., transient S3 timeout) resolves itself.

### No data appearing in Bronze tables

1. Confirm the simulation is running and publishing to Kafka topics.
2. Check consumer lag — the service polls every 1 second but only flushes every `BATCH_INTERVAL_SECONDS` (default 10s).
3. Verify `DELTA_BASE_PATH` and `S3_ENDPOINT_URL` are set correctly for your environment.
4. Check that MinIO is reachable and the `rideshare-bronze` bucket exists.

### `AWS_S3_ALLOW_UNSAFE_RENAME` warning

This is expected. The `deltalake` library requires this flag for S3/MinIO because S3 does not support atomic rename operations. It is set automatically whenever `DELTA_BASE_PATH` starts with `s3://` or `s3a://`.

### Messages landing in DLQ unexpectedly

If `DLQ_ENABLED=true` and `DLQ_VALIDATE_JSON=true`, any message that fails UTF-8 decoding or JSON parsing is routed to the DLQ instead of the main Bronze table. Inspect `dlq_bronze_{topic}` tables to find the `error_type` and `original_payload`.

### Tables missing from Trino after startup

Bronze Ingestion eagerly creates all Delta tables with empty `_delta_log/` metadata on startup (before any Kafka messages arrive). If Trino cannot see a table, re-run the Trino table registration script:

```bash
docker compose -f infrastructure/docker/compose.yml exec airflow-worker python /opt/airflow/scripts/register-trino-tables.py
```

Note: DBT views (`materialized='view'`) cannot be registered as Trino Delta tables.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: Bronze schema design, DLQ routing, at-least-once semantics
- [services/airflow/README.md](../airflow/README.md) — Airflow DAGs that consume Bronze tables for Silver/Gold transforms
- [services/kafka/README.md](../kafka/README.md) — Kafka broker that bronze-ingestion consumes from
- [services/stream-processor/README.md](../stream-processor/README.md) — Parallel consumer for real-time Redis/WebSocket fan-out
