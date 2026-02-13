# CONTEXT.md — Bronze Ingestion

## Purpose

Implements the bronze layer of the medallion lakehouse architecture. Consumes raw messages from 8 Kafka topics, adds metadata columns, and writes batches to partitioned Delta Lake tables in S3/MinIO storage. Provides at-least-once delivery semantics by committing Kafka offsets only after successful Delta writes.

## Responsibility Boundaries

- **Owns**: Raw data ingestion from Kafka to Delta Lake, metadata enrichment (partition/offset/timestamp tracking), batch accumulation and write orchestration, dead letter queue routing for malformed messages
- **Delegates to**: Kafka for message ordering and delivery, Delta Lake (delta-rs) for transaction log management and ACID guarantees, MinIO/S3 for object storage
- **Does not handle**: Schema validation against Avro/Protobuf definitions, data transformation or cleansing (deferred to silver layer), metrics export (future enhancement), backpressure or dynamic scaling

## Key Concepts

**Metadata Enrichment**: Every raw message gets 5 additional columns (`_kafka_partition`, `_kafka_offset`, `_kafka_timestamp`, `_ingested_at`, `_ingestion_date`) to enable lineage tracking and temporal queries.

**Batch Write Semantics**: Messages accumulate in memory for `BATCH_INTERVAL_SECONDS` (default 10s), then all topics are flushed atomically. Offsets commit only after successful Delta write, ensuring reprocessing on failure.

**Dead Letter Queue (DLQ)**: Optional routing of malformed messages (encoding errors, JSON parse failures) to topic-specific DLQ Delta tables (`dlq_bronze_{topic}`). Preserves original payload, Kafka metadata, and error details for forensic analysis.

**Table Initialization**: Pre-creates empty Delta tables for all topics on startup to ensure `_delta_log/` metadata exists before first message arrives, preventing downstream checks from failing.

## Non-Obvious Details

**Why delta-rs instead of Spark**: Eliminates JVM overhead and cluster initialization latency. Single Python process achieves 94% memory reduction vs Spark Structured Streaming (256 MB vs 4 GB) for this I/O-bound workload.

**Offset commit timing**: `enable.auto.commit=False` requires manual commit after Delta write. Uncommitted offsets on crash cause message reprocessing, but Delta Lake's idempotency (via append mode) prevents duplicates in many scenarios.

**Health endpoint error recovery**: The `/health` endpoint returns unhealthy after write failures, but resets to healthy on the next successful write. This allows transient errors (network blips, MinIO restarts) to self-heal without manual intervention.

**SASL/PLAINTEXT dual support**: Security protocol is configurable but defaults to PLAINTEXT. SASL credentials are only applied when `security_protocol != "PLAINTEXT"`, avoiding auth errors in local dev environments.

## Related Modules

- **[services/bronze-ingestion/src](src/CONTEXT.md)** — Implementation layer containing the actual ingestion service, Kafka consumer, and Delta writer components
- **[schemas/lakehouse/schemas](../../schemas/lakehouse/schemas/CONTEXT.md)** — Defines the Bronze table schemas that this service uses to initialize Delta tables
- **[services/kafka](../kafka/CONTEXT.md)** — Kafka topic definitions that this service consumes from; topic configuration affects ingestion behavior
- **[services/airflow/dags](../airflow/dags/CONTEXT.md)** — Monitors DLQ tables created by this service; triggers alerts when error thresholds are exceeded
- **[tools/dbt/models/staging](../../tools/dbt/models/staging/CONTEXT.md)** — Consumes Bronze Delta tables created by this service for Silver layer transformations
