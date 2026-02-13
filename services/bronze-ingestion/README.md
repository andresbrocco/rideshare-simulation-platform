# Bronze Ingestion

> Kafka-to-Delta ingestion service for the Bronze layer with at-least-once semantics

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka broker address |
| `KAFKA_CONSUMER_GROUP` | `bronze-ingestion` | Consumer group ID |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | Security protocol (PLAINTEXT, SASL_PLAINTEXT) |
| `KAFKA_SASL_MECHANISM` | `PLAIN` | SASL authentication mechanism |
| `KAFKA_SASL_USERNAME` | `` | Kafka SASL username (from secrets) |
| `KAFKA_SASL_PASSWORD` | `` | Kafka SASL password (from secrets) |
| `DELTA_BASE_PATH` | `s3a://rideshare-bronze` | Base path for Delta tables |
| `BATCH_INTERVAL_SECONDS` | `10` | Batch write interval |
| `KAFKA_POLL_TIMEOUT_MS` | `1000` | Kafka poll timeout |
| `S3_ENDPOINT` | `http://minio:9000` | S3/MinIO endpoint URL |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3/MinIO access key (from MINIO_ROOT_USER) |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3/MinIO secret key (from MINIO_ROOT_PASSWORD) |
| `AWS_REGION` | `us-east-1` | AWS region |
| `BRONZE_BUCKET` | `rideshare-bronze` | S3 bucket name |
| `DLQ_ENABLED` | `true` | Enable Dead Letter Queue routing |
| `DLQ_VALIDATE_JSON` | `false` | Validate JSON structure (strict mode) |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with Kafka and MinIO status |

**Health Endpoint Response:**
```bash
curl http://localhost:8086/health
```

```json
{
  "status": "healthy",
  "last_write": "2026-02-13T14:32:15.123456Z",
  "messages_written": 1234,
  "dlq_messages": 5,
  "errors": 0
}
```

**Status Codes:**
- `200 OK` - Service is healthy (errors == 0)
- `503 Service Unavailable` - Service is unhealthy (errors > 0)

### Ports

| Port | Service | Description |
|------|---------|-------------|
| `8086` | HTTP | Health endpoint (mapped from container 8080) |

### Kafka Topics Consumed

The service subscribes to all core event topics:

- `gps_pings` - Driver location updates
- `trips` - Trip lifecycle events
- `driver_status` - Driver availability changes
- `surge_updates` - Dynamic pricing updates
- `ratings` - Trip ratings
- `payments` - Payment transactions
- `driver_profiles` - Driver profile updates
- `rider_profiles` - Rider profile updates

### Prerequisites

**Dependencies:**
- Kafka broker (with SASL authentication)
- MinIO/S3 (for Delta table storage)
- Schema Registry (for Avro schema validation, if enabled)

**Startup Order:**
1. `secrets-init` - Seeds credentials from LocalStack Secrets Manager
2. `kafka-init` - Creates Kafka topics
3. `minio-init` - Creates S3 buckets
4. `bronze-ingestion` - This service

## Common Tasks

### Start the Service

```bash
# Start with data-pipeline profile
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d bronze-ingestion

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f bronze-ingestion
```

### Monitor Ingestion

```bash
# Check health status
curl http://localhost:8086/health

# View message counts and last write time
curl -s http://localhost:8086/health | jq '.messages_written, .last_write'

# Check for DLQ messages (malformed data)
curl -s http://localhost:8086/health | jq '.dlq_messages'
```

### Query Bronze Tables

```bash
# List Delta tables in MinIO
aws --endpoint-url http://localhost:9000 s3 ls s3://rideshare-bronze/

# Query via Trino (requires data-pipeline profile)
docker exec -it rideshare-trino trino --catalog iceberg --schema bronze
```

```sql
-- Example: Query recent GPS pings
SELECT * FROM iceberg.bronze.gps_pings
ORDER BY _metadata.kafka_timestamp DESC
LIMIT 10;

-- Check DLQ for failed messages
SELECT error_type, COUNT(*) as error_count
FROM iceberg.bronze.dead_letter_queue
GROUP BY error_type;
```

### Manually Test Kafka Consumption

```bash
# Produce test message to Kafka
docker exec -it rideshare-kafka kafka-console-producer \
  --broker-list kafka:29092 \
  --topic gps_pings

# Paste JSON payload:
{"driver_id": "test-123", "lat": -23.550520, "lng": -46.633308, "timestamp": "2026-02-13T14:30:00Z"}
```

### Restart with Different Batch Interval

```bash
# Stop service
docker compose -f infrastructure/docker/compose.yml stop bronze-ingestion

# Override batch interval (e.g., 30 seconds)
BATCH_INTERVAL_SECONDS=30 \
docker compose -f infrastructure/docker/compose.yml up -d bronze-ingestion
```

## Troubleshooting

### Service Unhealthy (503 Response)

**Symptom:**
```bash
$ curl http://localhost:8086/health
{"status": "unhealthy", "errors": 1, ...}
```

**Common Causes:**
1. **Kafka connection failure** - Check `KAFKA_BOOTSTRAP_SERVERS` and SASL credentials
2. **MinIO unreachable** - Verify `S3_ENDPOINT` and MinIO service health
3. **Delta write failure** - Check MinIO bucket exists and credentials are correct

**Debugging:**
```bash
# Check service logs for exceptions
docker compose -f infrastructure/docker/compose.yml logs --tail=50 bronze-ingestion

# Test Kafka connectivity
docker exec -it rideshare-kafka kafka-broker-api-versions \
  --bootstrap-server kafka:29092 \
  --command-config /tmp/kafka_client.properties

# Test MinIO connectivity
docker exec -it rideshare-bronze-ingestion curl http://minio:9000/minio/health/live
```

### No Messages Being Ingested

**Symptom:**
```bash
$ curl -s http://localhost:8086/health | jq '.messages_written'
0
```

**Check:**
1. **Kafka topics have data** - Verify upstream producers (simulation service)
2. **Consumer group not committed** - Check Kafka consumer group lag
3. **Service just started** - Wait for `BATCH_INTERVAL_SECONDS` (default 10s)

**Debugging:**
```bash
# Check if topics exist and have messages
docker exec -it rideshare-kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list kafka:29092 --topic gps_pings

# Check consumer group lag
docker exec -it rideshare-kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --group bronze-ingestion \
  --describe
```

### DLQ Messages Increasing

**Symptom:**
```bash
$ curl -s http://localhost:8086/health | jq '.dlq_messages'
42  # Non-zero and growing
```

**Cause:** Malformed messages failing UTF-8 decoding or JSON validation (if `DLQ_VALIDATE_JSON=true`)

**Investigation:**
```sql
-- Query DLQ in Trino to see error types
SELECT error_type, error_message, kafka_topic, COUNT(*) as count
FROM iceberg.bronze.dead_letter_queue
GROUP BY error_type, error_message, kafka_topic
ORDER BY count DESC;

-- Inspect specific failed messages
SELECT original_payload, error_message
FROM iceberg.bronze.dead_letter_queue
WHERE error_type = 'JSON_PARSE_ERROR'
LIMIT 5;
```

### Delta Table Schema Mismatch

**Symptom:** Service logs show schema evolution errors

**Resolution:**
```bash
# Stop service
docker compose -f infrastructure/docker/compose.yml stop bronze-ingestion

# Reset Delta tables (WARNING: deletes all data)
docker exec -it rideshare-minio-client mc rm --recursive --force minio/rideshare-bronze/

# Restart (tables will be reinitialized)
docker compose -f infrastructure/docker/compose.yml up -d bronze-ingestion
```

### Memory Issues (OOM)

**Symptom:** Container restarts frequently

**Tuning:**
```yaml
# In compose.yml, increase memory limit
deploy:
  resources:
    limits:
      memory: 512m  # Increase from 256m
```

Reduce batch interval to write smaller batches more frequently:
```bash
BATCH_INTERVAL_SECONDS=5 docker compose -f infrastructure/docker/compose.yml up -d bronze-ingestion
```

## Architecture Notes

### At-Least-Once Semantics

- Kafka offsets committed **after** successful Delta write
- Retries on transient failures (network, MinIO backpressure)
- Duplicate messages possible but idempotency handled downstream in Silver/Gold layers

### Dead Letter Queue (DLQ)

- **Encoding Errors:** Non-UTF-8 messages routed to `dead_letter_queue` table
- **JSON Validation:** Optional strict mode (`DLQ_VALIDATE_JSON=true`) rejects malformed JSON
- **Metadata Preserved:** Original payload, Kafka offset, partition, and error details stored

### Batch Processing

- Messages buffered in-memory until `BATCH_INTERVAL_SECONDS` elapsed
- All accumulated batches flushed atomically per topic
- Graceful shutdown flushes remaining messages

### Delta Table Initialization

On startup, the service initializes Delta tables for all subscribed topics:
- Creates S3 bucket paths (`s3a://rideshare-bronze/<topic>/`)
- Writes empty Delta `_delta_log/` metadata
- DLQ table initialized as `dead_letter_queue`

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture patterns and error handling details
- [Simulation Service](../simulation/README.md) - Upstream Kafka producer
- [Stream Processor](../stream-processor/README.md) - Parallel consumer for real-time WebSocket
- [Airflow DAGs](../airflow/dags/README.md) - Bronze → Silver ETL orchestration
- [Trino](../trino/README.md) - Query engine for Bronze layer Delta tables
