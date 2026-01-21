# CONTEXT.md — Framework

## Purpose

Provides a Template Method base class for all Spark Structured Streaming jobs that ingest raw Kafka events into Bronze layer Delta tables. Encapsulates the common Kafka-to-Delta streaming pipeline logic while allowing job-specific customization through abstract methods.

## Responsibility Boundaries

- **Owns**: Spark readStream configuration, Kafka consumer setup, Delta writeStream orchestration, metadata column injection (_kafka_partition, _kafka_offset, _kafka_timestamp, _ingested_at), checkpoint management, streaming query lifecycle (start/stop/await)
- **Delegates to**: Subclasses for topic selection, Bronze table path, batch processing logic, partition strategy
- **Does not handle**: Schema parsing (remains raw JSON string), data validation, dead letter queue writes (handled by ErrorHandler), Silver/Gold layer transformations

## Key Concepts

**Template Method Pattern**: `BaseStreamingJob` implements the full streaming pipeline in `start()`, calling abstract methods (`topic_name`, `bronze_table_path`, `process_batch`) that subclasses must define. This ensures all jobs follow the same Kafka→Delta flow while customizing data handling.

**Dual-Write Pattern**: The `start()` method configures `foreachBatch(self.process_batch)` but writes to `self.bronze_table_path`. Subclasses implement `process_batch()` to manually write batches (usually for partitioning), creating a potential double-write scenario. The framework expects subclasses to either write inside `process_batch()` OR rely on the outer writeStream target, not both.

**Checkpoint Recovery**: `recover_from_checkpoint()` is a hook for offset recovery logic but is not automatically called by the framework. Subclasses must explicitly invoke it if needed before calling `start()`.

## Non-Obvious Details

The `_raw_value` column contains the unparsed JSON string from Kafka. Schema parsing happens in Silver layer transformations, not here. This keeps Bronze layer as close to raw source data as possible.

Trigger modes are either `availableNow` (batch) or `processingTime` (micro-batch interval), controlled by `CheckpointConfig.trigger_interval`. Setting "availableNow" enables one-time batch processing for backfills.

Subclasses that override `partition_columns` must handle partitioning themselves in `process_batch()` by calling `partitionBy()` on their write builder. The base class does not automatically partition writes.
