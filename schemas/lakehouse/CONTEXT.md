# CONTEXT.md — Lakehouse

## Purpose

Defines PySpark schemas for the Bronze layer of a medallion lakehouse architecture. Schemas map 1:1 with Kafka event topics to ingest raw simulation events into Delta Lake with minimal transformation.

## Responsibility Boundaries

- **Owns**: PySpark StructType definitions for Bronze tables, standard field conventions (tracing + metadata), Delta Lake configuration utilities
- **Delegates to**: Kafka schemas in `schemas/kafka/` (source of truth for event structure), Spark streaming jobs (actual ingestion), DBT (Silver/Gold transformations)
- **Does not handle**: Schema evolution logic, data validation rules, or business transformations (those belong in Silver layer)

## Key Concepts

**Bronze Layer**: First stage in medallion architecture where raw events land from Kafka. Preserves data fidelity with append-only writes.

**Standard Fields**: Every Bronze table includes two categories:
- Tracing fields (nullable): `session_id`, `correlation_id`, `causation_id` for distributed tracing
- Metadata fields (non-nullable): `_ingested_at`, `_kafka_partition`, `_kafka_offset` for exactly-once processing and audit trails

**Source Alignment**: Field names and types match JSON schemas in `schemas/kafka/*.json` exactly. Type mappings follow PySpark conventions (UUIDs as StringType, ISO timestamps as TimestampType, nested arrays for GeoJSON).

**Dead Letter Queue**: Failed ingestion records captured in `dlq_schema` with original payload preserved for reprocessing.

**Delta Lake Features**: Bronze tables enable Change Data Feed (CDC for incremental processing), auto-optimize (file compaction), and date-based partitioning by `_ingestion_date`.

## Non-Obvious Details

Tracing fields are nullable because not all events originate from user requests (e.g., system-generated surge updates). Metadata fields are non-nullable because they're added during ingestion and critical for exactly-once semantics.

The `DeltaConfig` utility uses SQL ALTER TABLE commands rather than DataFrame write options because features must be enabled on existing tables post-creation.

## Related Modules

- **[../kafka](../kafka/CONTEXT.md)** — Schema source; lakehouse PySpark schemas must align with Kafka JSON schemas
- **[services/spark-streaming](../../services/spark-streaming/CONTEXT.md)** — Schema consumer; 2 consolidated streaming jobs apply these schemas during Bronze ingestion to 8 topic tables
