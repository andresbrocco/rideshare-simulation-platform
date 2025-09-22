# Databricks Bronze Layer Streaming

This directory contains Databricks Structured Streaming jobs that consume events from Confluent Cloud Kafka and write to Delta Lake tables in Unity Catalog.

## Purpose

Bronze layer streaming jobs ingest events from Kafka topics and write them to Delta Lake in their raw form. The implementation:

- Connects to Confluent Cloud Kafka with SASL_SSL authentication
- Reads streaming events with backpressure control
- Writes to Delta Lake in append mode with exactly-once semantics
- Extracts distributed tracing fields for end-to-end observability
- Handles malformed messages gracefully without failing the stream

## Directory Structure

```
databricks/
├── README.md                        # This file
├── notebooks/                       # Databricks notebooks for streaming jobs
│   └── bronze_streaming_setup.py   # Main streaming setup notebook
├── config/                          # Configuration modules
│   └── kafka_config.py             # Kafka connection configuration
├── utils/                           # Utility functions
│   └── streaming_utils.py          # Checkpoint, metadata, error handling utilities
└── tests/                           # Unit tests
    └── test_bronze_streaming_setup.py
```

## Dual Consumer Pattern

This implementation follows a **dual Kafka consumer pattern**:

1. **Databricks Structured Streaming** (this directory): Consumes from Kafka and writes to Delta Lake for batch analytics
2. **stream-processor service**: Consumes from Kafka and publishes to Redis pub/sub for real-time visualization

Both consumers use **independent consumer groups**, ensuring no conflicts or duplicate processing:
- Databricks consumer group: `databricks-bronze-consumer`
- Stream-processor consumer group: `stream-processor-redis`

## Kafka Topics → Bronze Tables

| Topic | Bronze Table | Description |
|-------|-------------|-------------|
| trip_events | rideshare.bronze.trip_events | Trip lifecycle events (requested, matched, completed) |
| gps_pings | rideshare.bronze.gps_pings | Driver GPS location updates |
| driver_status | rideshare.bronze.driver_status | Driver availability changes |
| surge_updates | rideshare.bronze.surge_updates | Surge pricing updates per zone |
| ratings | rideshare.bronze.ratings | Trip ratings submitted by riders |
| payments | rideshare.bronze.payments | Payment transactions |
| driver_profiles | rideshare.bronze.driver_profiles | Driver profile updates (SCD Type 2) |
| rider_profiles | rideshare.bronze.rider_profiles | Rider profile updates (SCD Type 2) |

## Configuration

### Databricks Secrets

Store Confluent Cloud credentials in Databricks secrets:

```bash
# Create secret scope (one-time setup)
databricks secrets create-scope --scope kafka

# Add secrets
databricks secrets put --scope kafka --key bootstrap_servers
# Value: pkc-xxxxx.us-east-1.aws.confluent.cloud:9092

databricks secrets put --scope kafka --key api_key
# Value: <your-confluent-api-key>

databricks secrets put --scope kafka --key api_secret
# Value: <your-confluent-api-secret>
```

### Checkpoint Storage

Checkpoints are stored in S3 at: `s3://rideshare-bronze-checkpoints/bronze/{topic_name}/`

**Critical**: Each streaming query has a **unique checkpoint location** - never share checkpoints between queries.

## Usage

### Running in Databricks

1. Upload `bronze_streaming_setup.py` to Databricks workspace
2. Ensure Databricks Runtime 16.4+ is configured
3. Configure secrets (see Configuration section)
4. Run the notebook:

```python
# Start all bronze streams
streams = start_all_bronze_streams()

# Check stream status
for stream in streams:
    print(stream.status)

# Stop all streams when done
stop_all_streams()
```

### Running Tests Locally

```bash
./venv/bin/pytest databricks/tests/test_bronze_streaming_setup.py -v
```

## Streaming Configuration

### Backpressure Control
- `maxOffsetsPerTrigger=10000`: Limits records per micro-batch to prevent overload

### Fault Tolerance
- `failOnDataLoss=false`: Prevents stream failure when Kafka data is aged out
- Checkpoints in S3 enable exactly-once processing semantics
- Streaming queries auto-restart on failure (configure via Databricks jobs)

### Error Handling
- Malformed JSON handled gracefully using `get_json_object()` (returns null on error)
- Stream continues processing despite individual message failures

## Distributed Tracing

All events include distributed tracing fields:

| Field | Description |
|-------|-------------|
| `session_id` | Identifies the simulation session |
| `correlation_id` | Root request/event ID |
| `causation_id` | Immediate parent event ID |

## Ingestion Metadata

All bronze tables include:
- `_ingested_at`: Timestamp when record was written to Delta Lake
- Kafka metadata: `topic`, `partition`, `offset`, `timestamp`

## Production Considerations

1. Use **jobs compute**, not all-purpose compute, for streaming workloads
2. Configure **auto-restart** for streaming jobs
3. Monitor **checkpoint lag** to ensure processing keeps up
4. Set appropriate **retention** on Delta tables
5. Use Delta **optimization** (OPTIMIZE, Z-ORDER) for query performance

## References

- [Databricks Structured Streaming Checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)
- [Databricks Kafka Integration](https://docs.databricks.com/aws/en/structured-streaming/kafka)
- [Delta Lake Streaming Writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)
- [Confluent Cloud Documentation](https://docs.confluent.io/cloud/current/)
