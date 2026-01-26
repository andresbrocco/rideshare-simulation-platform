# CONTEXT.md — Spark Streaming

## Purpose

Bronze layer ingestion service that consumes events from Kafka topics and writes raw data to Delta Lake tables in S3. Provides fault-tolerant streaming with checkpoint recovery, dead letter queue (DLQ) routing for malformed messages, and configurable micro-batch processing.

## Responsibility Boundaries

- **Owns**: Kafka-to-Delta ingestion pipeline, checkpoint management, DLQ routing for parse/schema errors, micro-batch processing logic
- **Delegates to**: Kafka for event sourcing, S3/MinIO for data persistence, Schema Registry for schema validation
- **Does not handle**: Data transformation or business logic (Silver/Gold layers), event generation (simulation service), schema definition (schemas/kafka)

## Key Concepts

**Bronze Layer**: Raw event storage preserving original Kafka messages with ingestion metadata (_kafka_partition, _kafka_offset, _kafka_timestamp, _ingested_at, _ingestion_date).

**BaseStreamingJob**: Abstract framework class that each topic-specific job extends. Defines contract for topic_name, bronze_table_path, and process_batch method.

**DLQ (Dead Letter Queue)**: Failed messages (JSON parse errors, schema violations) route to topic-specific DLQ Delta tables for manual inspection and reprocessing.

**Checkpoint Recovery**: Spark Structured Streaming maintains offset checkpoints in S3 for exactly-once processing semantics. Jobs can recover from checkpoint after restarts.

**Micro-Batch Processing**: foreachBatch pattern processes Kafka messages in configurable intervals (default 10 seconds or availableNow for batch mode).

## Non-Obvious Details

Jobs run as consolidated Docker containers (2 containers by volume tier: high-volume for gps-pings, low-volume for 7 other topics), each with its own Spark session in local mode (no central cluster). This reduces memory footprint from ~6.1GB to ~1.5GB. The framework enforces partition-by-date strategy for high-volume topics (gps-pings, trips) to enable efficient downstream queries. Error handler creates DLQRecord objects but actual persistence happens via DLQHandler.write_to_dlq. Jobs can be executed standalone via __main__ block or orchestrated by Airflow/Databricks workflows.

## Related Modules

- **[schemas/kafka](../../schemas/kafka/CONTEXT.md)** — Event schema source; streaming jobs consume events conforming to these JSON schemas
- **[schemas/lakehouse](../../schemas/lakehouse/CONTEXT.md)** — Bronze schema target; PySpark schemas must align with Kafka schemas for consistent ingestion
- **[services/dbt](../dbt/CONTEXT.md)** — Downstream consumer; DBT staging models read from Bronze Delta tables created by streaming jobs
- **[services/airflow](../airflow/CONTEXT.md)** — Monitors DLQ tables written by streaming jobs to detect parsing failures
- **[config](../../config/CONTEXT.md)** — Uses partition counts defined in Kafka topic configs to optimize consumer parallelism
