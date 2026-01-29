# Spark Streaming - Bronze Layer Ingestion

> Spark Structured Streaming jobs consuming Kafka events and writing to Delta Lake Bronze layer

## Quick Reference

### Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `kafka:29092` | Yes |
| `SCHEMA_REGISTRY_URL` | Schema Registry endpoint | `http://schema-registry:8081` | Yes |
| `CHECKPOINT_BASE_PATH` | S3 path for checkpoint storage | `s3a://rideshare-checkpoints/` | Yes |
| `TRIGGER_INTERVAL` | Micro-batch interval | `10 seconds` | No |
| `S3_ENDPOINT` | MinIO/S3 endpoint | `http://minio:9000` | Yes (Docker config) |
| `S3_ACCESS_KEY` | S3 access key | `minioadmin` | Yes (Docker config) |
| `S3_SECRET_KEY` | S3 secret key | `minioadmin` | Yes (Docker config) |

**Note:** S3 credentials are configured via Spark config options in Docker Compose, not as environment variables in the Python jobs.

### Docker Services

Two Spark Structured Streaming jobs run continuously in Docker Compose:

| Service | Profile | Topics | Memory | Container Name |
|---------|---------|--------|--------|----------------|
| `bronze-ingestion-high-volume` | `data-pipeline` | `gps_pings` | 768m | `rideshare-bronze-ingestion-high-volume` |
| `bronze-ingestion-low-volume` | `data-pipeline` | `trips`, `driver_status`, `surge_updates`, `ratings`, `payments`, `driver_profiles`, `rider_profiles` | 768m | `rideshare-bronze-ingestion-low-volume` |

**Start Services:**
```bash
# Start data pipeline (includes Spark streaming jobs)
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f bronze-ingestion-high-volume
docker compose -f infrastructure/docker/compose.yml logs -f bronze-ingestion-low-volume

# Check status
docker compose -f infrastructure/docker/compose.yml ps
```

### Commands

**Run High-Volume Job (local development):**
```bash
cd services/spark-streaming
./venv/bin/python jobs/bronze_ingestion_high_volume.py
```

**Run Low-Volume Job (local development):**
```bash
cd services/spark-streaming
./venv/bin/python jobs/bronze_ingestion_low_volume.py
```

**Run via spark-submit (Docker):**
```bash
spark-submit \
  --master local[2] \
  --driver-memory 512m \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  /opt/spark_streaming/jobs/bronze_ingestion_high_volume.py
```

### Output Locations

**Bronze Delta Tables (MinIO):**
- `s3a://rideshare-bronze/bronze_gps_pings/`
- `s3a://rideshare-bronze/bronze_trips/`
- `s3a://rideshare-bronze/bronze_driver_status/`
- `s3a://rideshare-bronze/bronze_surge_updates/`
- `s3a://rideshare-bronze/bronze_ratings/`
- `s3a://rideshare-bronze/bronze_payments/`
- `s3a://rideshare-bronze/bronze_driver_profiles/`
- `s3a://rideshare-bronze/bronze_rider_profiles/`

**Checkpoints (MinIO):**
- `s3a://rideshare-checkpoints/gps_pings/` (high-volume job)
- `s3a://rideshare-checkpoints/` (low-volume job - per-topic subdirs)

**Dead Letter Queue (DLQ):**
- `s3a://rideshare-bronze/dlq_gps_pings/` (high-volume job)
- `s3a://rideshare-bronze/dlq/` (low-volume job)

### Health Checks

```bash
# Check if Spark jobs are running
docker exec rideshare-bronze-ingestion-high-volume pgrep -f 'spark-submit'
docker exec rideshare-bronze-ingestion-low-volume pgrep -f 'spark-submit'

# View Spark UI
# High-volume job: http://localhost:4041 (if port is exposed)
# Low-volume job: http://localhost:4042 (if port is exposed)
```

## Common Tasks

### Monitor Streaming Progress

```bash
# View streaming metrics in logs
docker compose -f infrastructure/docker/compose.yml logs -f bronze-ingestion-high-volume | grep "numInputRows"

# Check checkpoint metadata
aws --endpoint-url=http://localhost:9000 s3 ls s3://rideshare-checkpoints/gps_pings/
```

### Verify Bronze Data

```bash
# Connect to Spark Thrift Server
beeline -u jdbc:hive2://localhost:10000

# Query Bronze tables
SELECT COUNT(*) FROM delta.`s3a://rideshare-bronze/bronze_gps_pings/`;
SELECT COUNT(*) FROM delta.`s3a://rideshare-bronze/bronze_trips/`;
```

### Handle Checkpoint Issues

```bash
# Reset checkpoint (WARNING: reprocesses all data from earliest)
aws --endpoint-url=http://localhost:9000 s3 rm --recursive s3://rideshare-checkpoints/gps_pings/

# Restart job
docker compose -f infrastructure/docker/compose.yml restart bronze-ingestion-high-volume
```

### Debug Failed Batches

```bash
# Check DLQ for failed records
aws --endpoint-url=http://localhost:9000 s3 ls s3://rideshare-bronze/dlq_gps_pings/

# View DLQ records
aws --endpoint-url=http://localhost:9000 s3 cp s3://rideshare-bronze/dlq_gps_pings/partition_date=2026-01-28/ - --recursive
```

## Architecture

### Job Isolation Strategy

**High-Volume Job (gps_pings):**
- Handles 8 partitions in dev (32 in production)
- Isolated to prevent backpressure on low-volume topics
- 10-second micro-batches
- Dedicated checkpoint path

**Low-Volume Job (7 topics):**
- Consolidated job for efficient resource sharing
- Topics: trips (4 partitions), driver_status (2), surge_updates (2), ratings (2), payments (2), driver_profiles (1), rider_profiles (1)
- Topic-based routing to separate Bronze tables
- Shared checkpoint base path with topic-specific subdirs

### Framework Classes

**BaseStreamingJob** (`framework/base_streaming_job.py`)
- Abstract base class for all streaming jobs
- Kafka reader setup, checkpoint management, error handling
- Single-topic and multi-topic support

**MultiTopicStreamingJob** (`jobs/multi_topic_streaming_job.py`)
- Extends `BaseStreamingJob` for multi-topic consumption
- Routes messages to appropriate Bronze tables based on `topic` column
- All tables partitioned by `_ingestion_date`

**KafkaConfig** (`config/kafka_config.py`)
- Kafka consumer configuration
- Generates Spark readStream options
- Supports both single-topic and multi-topic subscribe patterns

**CheckpointConfig** (`config/checkpoint_config.py`)
- Checkpoint path and trigger interval configuration
- Enables exactly-once processing semantics

**ErrorHandler** (`utils/error_handler.py`)
- DLQ handling for malformed records
- Error logging and metrics

### Bronze Schema

All Bronze tables include Kafka metadata:

| Column | Type | Description |
|--------|------|-------------|
| `_raw_value` | String | Raw JSON from Kafka value field |
| `_kafka_partition` | Int | Kafka partition number |
| `_kafka_offset` | Long | Kafka offset |
| `_kafka_timestamp` | Timestamp | Kafka message timestamp |
| `_ingested_at` | Timestamp | Ingestion timestamp |
| `_ingestion_date` | String | Partition column (yyyy-MM-dd) |

## Prerequisites

**Services:**
- Kafka (port 29092)
- Schema Registry (port 8081)
- MinIO (ports 9000, 9001)

**Python Dependencies:**
- `pyspark>=3.5.0`
- `delta-spark>=3.0.0`

**Install:**
```bash
cd services/spark-streaming
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Testing

```bash
cd services/spark-streaming
./venv/bin/pytest

# Run with markers
./venv/bin/pytest -m unit
./venv/bin/pytest -m integration  # Requires Docker services
```

## Troubleshooting

### Job Not Consuming Messages

**Symptoms:** Streaming query shows 0 input rows

**Causes:**
1. Kafka topics not created
2. No messages published
3. Consumer group already at latest offset

**Resolution:**
```bash
# Check topics exist
docker exec rideshare-kafka kafka-topics --bootstrap-server kafka:29092 --list

# Check topic lag
docker exec rideshare-kafka kafka-consumer-groups --bootstrap-server kafka:29092 --group spark-streaming --describe

# Reset to earliest offsets (delete checkpoint)
aws --endpoint-url=http://localhost:9000 s3 rm --recursive s3://rideshare-checkpoints/gps_pings/
docker compose -f infrastructure/docker/compose.yml restart bronze-ingestion-high-volume
```

### S3 Connection Errors

**Symptoms:** `java.net.ConnectException: Connection refused (Connection refused)` or `org.apache.hadoop.fs.s3a.AWSClientIOException`

**Causes:**
1. MinIO not running
2. Incorrect S3 endpoint configuration
3. Network connectivity issues

**Resolution:**
```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# Verify S3 credentials in Spark config
docker compose -f infrastructure/docker/compose.yml config | grep s3a

# Restart MinIO
docker compose -f infrastructure/docker/compose.yml restart minio
```

### Checkpoint Corruption

**Symptoms:** `org.apache.spark.sql.streaming.StreamingQueryException: Checkpoint ... is corrupted`

**Causes:**
1. Incomplete checkpoint write
2. Schema evolution without checkpoint reset
3. Concurrent writes to checkpoint location

**Resolution:**
```bash
# Delete corrupted checkpoint
aws --endpoint-url=http://localhost:9000 s3 rm --recursive s3://rideshare-checkpoints/gps_pings/

# Restart job (will reprocess from earliest)
docker compose -f infrastructure/docker/compose.yml restart bronze-ingestion-high-volume
```

### Out of Memory

**Symptoms:** `java.lang.OutOfMemoryError: Java heap space`

**Causes:**
1. Batch size too large
2. Insufficient driver memory
3. Data skew in partitions

**Resolution:**
```bash
# Increase driver memory in compose.yml
# Edit infrastructure/docker/compose.yml:
# --driver-memory 768m  (increase from 512m)

# Decrease batch interval to reduce batch size
# Set TRIGGER_INTERVAL=5 seconds

# Restart service
docker compose -f infrastructure/docker/compose.yml up -d bronze-ingestion-high-volume
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture and design decisions
- [../../schemas/kafka/](../../schemas/kafka/) - Kafka event schemas
- [../../schemas/lakehouse/](../../schemas/lakehouse/) - Bronze layer PySpark schemas
- [../dbt/](../dbt/) - Silver/Gold transformations (consumes Bronze tables)
- [../../infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker service definitions
