# CONTEXT.md — Lakehouse Schemas

## Purpose

Defines PySpark `StructType` schemas for all Bronze Delta Lake tables and the Dead Letter Queue (DLQ) table. These schemas are the authoritative column-level contract between the bronze-ingestion service and downstream consumers (Silver transformation, Trino table registration).

## Responsibility Boundaries

- **Owns**: PySpark schema definitions for each Bronze event type and the DLQ
- **Delegates to**: `schemas/lakehouse` (parent package exposes table-name-to-schema mappings used by registration scripts)
- **Does not handle**: Silver or Gold schemas (those are defined via DBT models), Kafka Avro schemas (defined in `schemas/kafka/`)

## Key Concepts

**Shared field groups** — Two private helpers compose into every Bronze schema:
- `_tracing_fields()`: `session_id`, `correlation_id`, `causation_id` — distributed tracing correlation fields added by the simulation engine
- `_metadata_fields()`: `_ingested_at`, `_kafka_partition`, `_kafka_offset` — ingestion provenance added by the bronze-ingestion service, not present in the originating Kafka event

**DLQ schema** — `dlq_schema.py` defines the Dead Letter Queue table, which captures raw failed events as `original_payload` (string) alongside error metadata. It reuses the tracing and metadata field names but is structurally independent of the domain schemas.

**Nullable conventions** — Event-type-specific optional fields (e.g., `driver_id` on trip events before a driver is assigned, `cancelled_by` / `cancellation_reason`) are nullable. Core identity and timestamp fields are non-nullable. The `_metadata_fields` are always non-nullable since they are set at ingestion time.

## Non-Obvious Details

- The `__init__.py` currently exports only `dlq_schema`, not the domain table schemas. The domain schemas (`bronze_trips_schema`, `bronze_gps_pings_schema`, etc.) are imported directly by name from `schemas.lakehouse.schemas.bronze_tables` by the table registration script.
- `location` and coordinate fields are `ArrayType(DoubleType())` — `[longitude, latitude]` order following GeoJSON convention. Route geometry fields are `ArrayType(ArrayType(DoubleType()))` — a list of `[lon, lat]` pairs.
- `behavior_factor` on `bronze_rider_profiles_schema` is nullable because it is a simulation-internal DNA parameter and may not always be emitted.
