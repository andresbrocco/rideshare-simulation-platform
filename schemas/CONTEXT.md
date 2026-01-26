# CONTEXT.md — Schemas

## Purpose

Centralized schema definitions for Kafka event validation and lakehouse data ingestion. Ensures consistent data contracts between event producers (simulation) and consumers (stream processors, data platform).

## Responsibility Boundaries

- **Owns**: JSON Schema definitions for Kafka topics, PySpark schema definitions for Bronze layer tables, standard field definitions (tracing, metadata), DLQ schema for malformed events
- **Delegates to**: Confluent Schema Registry for runtime validation, Spark Structured Streaming for schema enforcement during ingestion
- **Does not handle**: Schema evolution logic (handled by Schema Registry), data transformation (handled by DBT in Silver/Gold layers)

## Key Concepts

**Dual Schema System** — Each event type has two schema definitions that must remain aligned:
- JSON Schema (kafka/*.json): Used for event validation at publish time and registered in Schema Registry
- PySpark StructType (lakehouse/schemas/bronze_tables.py): Used for parsing events during Spark ingestion to Bronze layer

**Standard Fields** — All events include:
- Tracing fields (session_id, correlation_id, causation_id): Enable distributed tracing across the simulation lifecycle
- Ingestion metadata (_ingested_at, _kafka_partition, _kafka_offset): Critical for exactly-once processing and partition-level recovery

**Source Alignment Contract** — Bronze schemas mirror Kafka schemas exactly with no transformations to preserve data fidelity. Type mappings follow strict conventions (string → StringType, ISO timestamp → TimestampType, number → DoubleType).

## Non-Obvious Details

The lakehouse/README.md provides documentation on Bronze table design, but schema alignment between Kafka and PySpark must be maintained manually. Changes to Kafka schemas require corresponding updates to Bronze schemas.

DLQ schema captures original payload as string to enable forensic analysis of malformed events without data loss.

## Related Modules

- **[services/simulation](../services/simulation/CONTEXT.md)** — Schema producer; simulation emits events conforming to Kafka JSON schemas
- **[services/spark-streaming](../services/spark-streaming/CONTEXT.md)** — Schema consumer; 2 consolidated streaming jobs use lakehouse PySpark schemas to parse and store events in 8 Bronze Delta tables
- **[config](../config/CONTEXT.md)** — Partition configuration companion; topic configs reference schema field names as partition keys
