# CONTEXT.md — Schemas

## Purpose

PySpark StructType definitions for Bronze layer tables in the medallion lakehouse. Each schema maps to a Kafka topic and defines the exact field structure used during streaming ingestion into Delta Lake.

## Responsibility Boundaries

- **Owns**: PySpark schema definitions for 8 Bronze tables (trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles) and DLQ table, reusable field factories for tracing and metadata columns
- **Delegates to**: Parent module for Delta Lake configuration utilities, Kafka schemas in `schemas/kafka/` for canonical field definitions
- **Does not handle**: Schema registration (done by ingestion jobs), runtime validation (handled by Spark), or schema evolution (managed by Delta Lake)

## Key Concepts

**Schema Factories**: Helper functions `_tracing_fields()` and `_metadata_fields()` generate standard field sets appended to every Bronze table. This ensures consistency across all schemas and centralizes field definitions.

**Nullability Semantics**: Tracing fields (session_id, correlation_id, causation_id) are nullable because system-generated events like surge updates lack user request context. Metadata fields (_ingested_at, _kafka_partition, _kafka_offset) are non-nullable as they're always injected during ingestion.

**Type Mappings**: Follows PySpark conventions: UUIDs as StringType, ISO timestamps as TimestampType, GeoJSON coordinates as ArrayType(DoubleType()), routes as nested arrays.

**DLQ Schema**: Dead letter queue captures ingestion failures with error context (error_message, error_type), original payload preservation for reprocessing, and Kafka provenance metadata.

## Non-Obvious Details

The `bronze_tables.py` file defines all table schemas but only exports utility functions via `__init__.py`. Actual schema imports happen directly in consuming code (bronze-ingestion jobs) by importing specific schema variables.

Tracing fields use the same structure across all events to enable distributed tracing queries in the Gold layer. The three-field pattern (session_id, correlation_id, causation_id) follows event sourcing tracing conventions where causation links commands to their triggering events.

## Related Modules

- **[schemas](../../CONTEXT.md)** — Parent schemas directory; this module provides PySpark implementations of schemas defined conceptually in the parent
- **[services/bronze-ingestion](../../../services/bronze-ingestion/CONTEXT.md)** — Primary consumer of these schemas; uses them to parse Kafka events and write Delta Lake tables
- **[services/simulation/src/events](../../../services/simulation/src/events/CONTEXT.md)** — Event factories that produce data matching these schemas; schema alignment ensures ingestion compatibility
