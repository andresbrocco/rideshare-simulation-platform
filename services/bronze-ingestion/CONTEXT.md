# CONTEXT.md — Bronze-Ingestion

## Purpose

Consumes all simulation event topics from Kafka and persists them as raw, unmodified JSON records in partitioned Delta Lake tables on S3/MinIO. This is the entry point of the medallion lakehouse: it preserves the original event payload without any transformation, so downstream Silver processing always has access to the source-of-truth data.

## Responsibility Boundaries

- **Owns**: Kafka consumption, schema validation decisions, writing raw events to Bronze Delta tables, routing malformed messages to DLQ Delta tables
- **Delegates to**: Delta Lake / PyArrow for table format and storage; S3/MinIO for object storage; Kafka Schema Registry is not used here — validation is local JSON Schema
- **Does not handle**: Parsing or transforming event fields (Silver's responsibility), offset management beyond synchronous commit after each batch flush

## Key Concepts

- **Bronze schema**: All tables share a single fixed schema — `_raw_value` (the raw UTF-8 JSON string), plus Kafka provenance columns (`_kafka_partition`, `_kafka_offset`, `_kafka_timestamp`, `_ingested_at`) and `_ingestion_date` used as the partition column. No event-specific fields are extracted at this layer.
- **Micro-batch loop**: Messages accumulate in memory and are flushed on a configurable interval (`BATCH_INTERVAL_SECONDS`, default 10s). Offsets are committed synchronously only after a successful Delta write, providing at-least-once delivery semantics.
- **DLQ (Dead Letter Queue)**: Optionally enabled via `DLQ_ENABLED`. Messages that fail UTF-8 decoding, JSON parsing, or JSON Schema validation are routed to parallel topic-specific DLQ Delta tables (`dlq_bronze_{topic}`) instead of being dropped or blocking the main pipeline.
- **Eager table initialization**: On startup, `DeltaWriter.initialize_tables()` creates all Bronze and DLQ Delta tables with `mode="ignore"` before any messages arrive. This ensures downstream registration scripts (e.g., Trino table registration) see all tables immediately, even for topics with no data yet.
- **AWS_S3_ALLOW_UNSAFE_RENAME**: Required by `deltalake` for S3/MinIO because S3 does not support atomic rename. Set unconditionally whenever an S3-based path is used.

## Non-Obvious Details

- Schema validation (`DLQ_VALIDATE_SCHEMA`) loads JSON Schema files from a mounted volume at `DLQ_SCHEMA_DIR` (default `/app/schemas`). Topics without a matching schema file silently pass through validation — there is no error for a missing schema file.
- The `commit()` method calls `consumer.commit(asynchronous=False)` regardless of whether the `messages` argument is populated. The argument is accepted but not actually used to select which offsets to commit — confluent-kafka commits the current consumer position.
- The health endpoint (`/health` on port 8080) resets the error counter to zero on any successful batch write, allowing recovery from transient S3 errors without a restart.
- `s3a://` and `s3://` paths are both treated as S3 targets; the `s3a://` prefix is the canonical form used by Hadoop-ecosystem tools and signals the need for storage options injection.
- DLQ tables are partitioned by `kafka_topic` only (no date partition), while main Bronze tables are partitioned by `_ingestion_date`.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/airflow](../airflow/CONTEXT.md) — Reverse dependency — Provides dbt_silver_transformation (DAG), dbt_gold_transformation (DAG), delta_maintenance (DAG) (+1 more)
