# Bronze Ingestion Service

A Python-based Kafka-to-Delta ingestion service that consumes from multiple Kafka topics and writes raw data to Delta Lake tables in the bronze layer.

## Overview

This service implements the bronze layer of a medallion lakehouse architecture. It consumes messages from 8 Kafka topics, adds metadata columns, and writes batches to Delta Lake tables partitioned by ingestion date.

## Features

- **Multi-topic consumption**: Subscribes to 8 rideshare platform topics (gps_pings, trips, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles)
- **Metadata enrichment**: Adds Kafka metadata (_kafka_partition, _kafka_offset, _kafka_timestamp) and ingestion metadata (_ingested_at, _ingestion_date)
- **Batch processing**: Configurable batch write interval (default: 10 seconds)
- **Delta Lake integration**: Uses delta-rs (deltalake library) for native Delta Lake writes
- **S3/MinIO support**: Configurable storage options for S3-compatible object storage
- **At-least-once semantics**: Commits Kafka offsets only after successful Delta write
- **Graceful shutdown**: Handles SIGINT/SIGTERM signals to flush remaining batches

## Architecture

```
Kafka Topics → KafkaConsumer → [Batch Buffer] → DeltaWriter → Delta Tables (S3/MinIO)
                                     ↓
                            Offset Commit (after write success)
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka broker connection string |
| `KAFKA_CONSUMER_GROUP` | `bronze-ingestion` | Consumer group ID |
| `BATCH_INTERVAL_SECONDS` | `10` | Batch write interval in seconds |
| `DELTA_BASE_PATH` | `s3a://rideshare-bronze` | Base path for Delta tables |
| `S3_ENDPOINT` | `http://minio:9000` | S3/MinIO endpoint URL |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3 access key |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3 secret key |
| `AWS_REGION` | `us-east-1` | AWS region |
| `BRONZE_BUCKET` | `rideshare-bronze` | S3 bucket name |
| `KAFKA_POLL_TIMEOUT_MS` | `1000` | Kafka poll timeout in milliseconds |

## Delta Table Schema

All bronze tables have the following schema:

| Column | Type | Description |
|--------|------|-------------|
| `_raw_value` | string | Raw JSON message from Kafka |
| `_kafka_partition` | int32 | Source Kafka partition |
| `_kafka_offset` | int64 | Kafka message offset |
| `_kafka_timestamp` | timestamp(us, UTC) | Kafka message timestamp |
| `_ingested_at` | timestamp(us, UTC) | Ingestion timestamp |
| `_ingestion_date` | string | Partition key (yyyy-MM-dd) |

Tables are partitioned by `_ingestion_date` for efficient querying and retention management.

## Output

Delta tables are written to:
```
s3a://rideshare-bronze/bronze_{topic}/
```

For example:
- `s3a://rideshare-bronze/bronze_trips/`
- `s3a://rideshare-bronze/bronze_gps_pings/`
- `s3a://rideshare-bronze/bronze_ratings/`

## Running

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/test_ingestion_core.py -v

# Run service (requires Kafka and S3/MinIO)
python -m src.main
```

### Docker

```bash
# Build image
docker build -t bronze-ingestion .

# Run container
docker run --rm \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:29092 \
  -e S3_ENDPOINT=http://minio:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  -p 8080:8080 \
  bronze-ingestion

# Test health endpoint
curl http://localhost:8080/health
```

## Docker Deployment

### Resource Limits

The service is designed to run with minimal resources:

| Resource | Limit | Rationale |
|----------|-------|-----------|
| Memory | 256 MB | Batch accumulation (~10 seconds x 60 events/sec x ~1 KB/event = ~600 KB buffer) |
| CPU | 0.5 cores | I/O-bound workload; librdkafka handles Kafka protocol efficiently |

**Comparison to Spark Streaming:**
- Spark (2 containers): 4 GB memory, no CPU limit
- Python (1 container): 256 MB memory, 0.5 CPU cores
- **Reduction:** 94% memory, controlled CPU usage

### Health Endpoint

The service exposes `GET /health` on port 8080 for Docker healthcheck:

```json
{"status": "healthy", "last_write": "2024-01-15T10:30:00+00:00", "messages_written": 150, "errors": 0}
```

- Returns HTTP 200 when healthy, 503 when unhealthy
- Unhealthy if no successful write in last 60 seconds
- Used by Docker HEALTHCHECK to restart unresponsive containers

### Docker Compose Example

```yaml
bronze-ingestion:
  build:
    context: ./services/bronze-ingestion
    dockerfile: Dockerfile
  ports:
    - "8080:8080"
  environment:
    KAFKA_BOOTSTRAP_SERVERS: kafka:29092
    S3_ENDPOINT: http://minio:9000
    AWS_ACCESS_KEY_ID: minioadmin
    AWS_SECRET_ACCESS_KEY: minioadmin
  deploy:
    resources:
      limits:
        memory: 256M
        cpus: '0.5'
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 10s
```

## Dependencies

- `confluent-kafka==2.13.0` - Kafka consumer client
- `deltalake==1.4.2` - Delta Lake reader/writer (delta-rs)
- `pyarrow>=15.0.0` - Arrow table manipulation
- `python-dateutil` - Date/time utilities
- `pytest>=7.0.0` - Testing framework

## Operational Behavior

### Batch Processing

Messages are accumulated in memory per topic. Every `BATCH_INTERVAL_SECONDS`:
1. All accumulated messages per topic are written to their respective Delta tables
2. Kafka consumer offsets are committed (only after successful writes)
3. Batch buffer is cleared

### Shutdown

On receiving SIGINT or SIGTERM:
1. Stop polling for new messages
2. Flush all remaining batches to Delta tables
3. Commit final offsets
4. Close Kafka consumer gracefully

### Error Handling

- Write failures: Exception raised, offsets NOT committed, service stops
- Kafka errors: KafkaException raised with error details
- Consumer rebalancing: Handled automatically by confluent-kafka

## Testing

Test suite covers:
- Topic subscription verification
- Metadata column injection
- Batch write interval timing
- Partition-by-date validation
- Offset commit semantics
- Schema compatibility with Spark implementation

Run tests:
```bash
pytest tests/test_ingestion_core.py -v --cov=src
```

## Troubleshooting

### Consumer lag

Check if batch interval is too long or message volume is too high:
```bash
kafka-consumer-groups --bootstrap-server kafka:29092 \
  --group bronze-ingestion \
  --describe
```

### Delta table access issues

Verify S3 credentials and endpoint:
```python
from deltalake import DeltaTable
dt = DeltaTable(
    "s3a://rideshare-bronze/bronze_trips",
    storage_options={
        'AWS_ENDPOINT_URL': 'http://minio:9000',
        'AWS_ACCESS_KEY_ID': 'minioadmin',
        'AWS_SECRET_ACCESS_KEY': 'minioadmin',
        'AWS_REGION': 'us-east-1',
        'AWS_ALLOW_HTTP': 'true',
    }
)
print(dt.to_pyarrow_table().schema)
```

### Missing partitions

Ensure messages are flowing from Kafka and batch interval has elapsed:
```bash
# List partitions in Delta table
aws s3 ls s3://rideshare-bronze/bronze_trips/ --recursive \
  --endpoint-url http://minio:9000
```

## Design Decisions

### Why delta-rs instead of PySpark?

- **Lightweight**: No JVM or Spark cluster required
- **Fast startup**: Immediate processing, no cluster initialization
- **Resource efficient**: Lower memory footprint for simple ingestion
- **Simpler deployment**: Single Python process, easier to containerize

### Why batch writes instead of micro-batches?

- **Efficiency**: Reduces number of Delta transaction log entries
- **Cost**: Fewer S3 API calls (write + commit operations)
- **Performance**: Amortizes write overhead across multiple messages
- **Configurable**: Can be tuned based on latency requirements

### Why manual offset commits?

- **Exactly-once semantics**: Only commit after successful Delta write
- **Reprocessing safety**: Failed writes can be retried from last committed offset
- **Data integrity**: No data loss even on service restart

## Future Enhancements

- [ ] Schema validation against Avro/Protobuf schemas
- [ ] Metrics export (Prometheus)
- [ ] Dead letter queue for malformed messages
- [ ] Backpressure handling
- [ ] Dynamic topic discovery
- [ ] Checkpoint state to Redis for faster recovery
