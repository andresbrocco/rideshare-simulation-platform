# CONTEXT.md — bronze-ingestion/src

## Purpose

Implements the Bronze layer ingestion pipeline: consumes raw Kafka events across 8 topics and writes them as-is (plus provenance metadata) to partitioned Delta Lake tables on S3/MinIO. Malformed messages are routed to parallel DLQ Delta tables rather than being dropped or causing consumer stalls.

## Responsibility Boundaries

- **Owns**: Kafka offset commit lifecycle, Delta table initialization, Bronze schema definition, DLQ routing logic, health state tracking
- **Delegates to**: `deltalake` / `pyarrow` for Delta writes, `confluent_kafka` for consumer management, `jsonschema` for JSON Schema validation
- **Does not handle**: Silver/Gold transformations, Trino registration, schema evolution, deduplication, or event parsing beyond what validation requires

## Key Concepts

**Bronze schema**: Every record stores `_raw_value` (raw UTF-8 JSON string) alongside Kafka provenance fields (`_kafka_partition`, `_kafka_offset`, `_kafka_timestamp`, `_ingested_at`) and `_ingestion_date` (string, used as the Delta partition column). The raw payload is intentionally preserved verbatim; no fields are extracted at this layer.

**DLQ routing**: Messages failing any validation tier are written to `dlq_bronze_{topic}` tables (same S3 bucket, separate paths) and excluded from the main Bronze write. The validation chain is: (1) UTF-8 decoding → (2) JSON parse (optional, `DLQ_VALIDATE_JSON`) → (3) JSON Schema check (optional, `DLQ_VALIDATE_SCHEMA`). Topics without a registered schema file pass through silently.

**Batch-flush loop**: `IngestionService` accumulates messages per topic in memory for up to `BATCH_INTERVAL_SECONDS` (default 10s), then flushes valid records to Bronze and DLQ records to their respective tables in one pass. Offsets are committed only after a successful flush — manual commit with `enable.auto.commit=False`.

**Table pre-initialization**: On startup, `DeltaWriter.initialize_tables()` and `DLQWriter.initialize_tables()` create empty Delta tables (mode `"ignore"`) for all 8 topics. This ensures `_delta_log/` metadata exists immediately so downstream table-registration scripts don't fail before any messages arrive.

**Lazy consumer**: `KafkaConsumer._ensure_consumer()` defers `Consumer` construction until the first `poll()` call. SASL config is only added when `security_protocol != "PLAINTEXT"`, so the same code path works for both dev (PLAINTEXT) and prod (SASL_SSL).

## Non-Obvious Details

- `AWS_S3_ALLOW_UNSAFE_RENAME=true` is set unconditionally for S3 paths. This is required by `deltalake` when writing to object stores that lack atomic rename (S3, MinIO) — without it Delta commits fail.
- The `commit()` method calls `self._consumer.commit(asynchronous=False)` regardless of whether `messages` is provided or not; the `messages` parameter branch distinction is currently a no-op. Offsets committed are the last polled positions, not per-message.
- Health state resets `errors` to 0 on every successful write (`record_write()`), so the service can self-recover from transient S3 failures without restart.
- DLQ records include `session_id`, `correlation_id`, and `causation_id` fields (nullable) for distributed tracing correlation, even though the ingestion service itself does not populate them — they are reserved for future enrichment.
- `_ingestion_date` is a plain string (format `YYYY-MM-DD`), not a date type, because `deltalake`'s partition column handling with PyArrow works more reliably with string partitions than with date types across S3-compatible storage backends.
