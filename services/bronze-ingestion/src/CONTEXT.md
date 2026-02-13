# CONTEXT.md — Bronze Ingestion

## Purpose

Bronze ingestion consumes raw events from Kafka topics and persists them as partitioned Delta Lake tables in S3/MinIO storage. This is the first stage of the medallion architecture, capturing immutable raw data with metadata for lineage tracking.

## Responsibility Boundaries

- **Owns**: Kafka consumption from 8 topics (gps_pings, trips, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles), Delta Lake table creation and writes, dead letter queue routing for malformed messages
- **Delegates to**: MinIO/S3 for object storage, Kafka for message ordering and delivery guarantees, Schema Registry (indirectly, through stream-processor validation)
- **Does not handle**: Schema validation (messages stored raw), data transformation (that's Silver layer), message deserialization beyond UTF-8 encoding

## Key Concepts

**Bronze Schema**: All tables share a fixed schema with metadata fields (_raw_value, _kafka_partition, _kafka_offset, _kafka_timestamp, _ingested_at, _ingestion_date). The `_raw_value` field stores the raw Kafka message payload as a string without parsing.

**Dead Letter Queue (DLQ)**: Optional routing of malformed messages to topic-specific `dlq_bronze_*` tables. Validation can check UTF-8 encoding (always) and JSON structure (optional via DLQ_VALIDATE_JSON). DLQ records preserve original payload, error type, and Kafka coordinates.

**Manual Commit Control**: Auto-commit is disabled. The service only commits offsets after successful Delta writes, ensuring at-least-once delivery semantics. Messages are batched by topic with a configurable time window (default 10s).

## Non-Obvious Details

The service initializes all 8 Delta tables on startup (via `DeltaTable.create` with `mode="ignore"`), even if no messages have arrived yet. This ensures downstream checks see `_delta_log/` metadata immediately rather than waiting for the first message per topic.

Storage options are conditionally applied only when `delta_base_path` starts with `s3://` or `s3a://`. Local file paths (used in tests) skip S3 configuration. The `AWS_S3_ALLOW_UNSAFE_RENAME` flag is required for MinIO compatibility with Delta Lake's atomic rename operations.

Health endpoint returns 503 (unhealthy) whenever `errors > 0`, but a successful write resets the error count to zero, allowing recovery from transient failures without restart.

## Related Modules

- **[services/simulation/src/kafka](../../simulation/src/kafka)** — Kafka producer that publishes events consumed by this ingestion service; event structure must match Bronze schema expectations
- **[schemas/lakehouse/schemas](../../../schemas/lakehouse/schemas/CONTEXT.md)** — Defines PySpark Bronze schemas that conceptually align with the raw storage format used here
- **[services/airflow/dags](../../airflow/dags/CONTEXT.md)** — Queries DLQ tables created by this service to monitor ingestion health and alert on errors
