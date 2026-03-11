# CONTEXT.md — Schemas

## Purpose

Cross-cutting schema contracts for the entire platform. This directory is the single source of truth for data shapes that cross service boundaries: Kafka event schemas validated by Schema Registry, PySpark struct definitions used in the Bronze lakehouse layer, the OpenAPI specification for the simulation REST/WebSocket API, and Delta Lake table configuration utilities.

## Responsibility Boundaries

- **Owns**: All cross-service data contracts — Kafka event JSON schemas, Bronze-layer PySpark struct types, DLQ table schema, Delta Lake feature configuration, OpenAPI specification
- **Delegates to**: Individual services that consume these schemas (simulation, stream-processor, bronze-ingestion, control-panel)
- **Does not handle**: Business logic, data transformation, validation enforcement at runtime (enforcement is the responsibility of each consumer)

## Key Concepts

- **Kafka schemas** (`schemas/kafka/`): JSON Schema Draft 2020-12 documents registered with Confluent Schema Registry. Each event carries three distributed-tracing correlation fields: `session_id` (simulation run), `correlation_id` (primary business entity, typically `trip_id`), and `causation_id` (the event that triggered this one).
- **Lakehouse schemas** (`schemas/lakehouse/`): PySpark `StructType` definitions for Bronze Delta tables, plus a standalone `DeltaConfig` utility that enables Change Data Feed (CDC), `autoOptimize`, and `autoCompact` on tables via `ALTER TABLE` SQL. These are packaged as a separate Python project (`lakehouse-schemas`) installable into PySpark environments.
- **API schema** (`schemas/api/openapi.json`): OpenAPI 3.1.0 spec for the simulation control panel. Authentication is via `X-API-Key` header (REST) and `Sec-WebSocket-Protocol: apikey.<key>` (WebSocket).
- **DLQ schema**: The dead-letter queue table captures `_kafka_partition`, `_kafka_offset`, `original_payload`, and the three correlation fields alongside error metadata — enabling replay and root-cause analysis of ingestion failures.

## Non-Obvious Details

- The `behavior_factor` field in `rider_profile_event.json` only appears on `rider.created` events (not `rider.updated`). Consumers should treat it as optional and not assume its presence on update events.
- GPS ping events carry both `route_progress_index` (progress along the trip route) and `pickup_route_progress_index` (progress along the pickup route) as separate nullable integers — both can be present simultaneously when a driver is en route to pick up a rider.
- The `platform_fee_percentage` in payment events is expressed as a decimal fraction in [0, 1], not a percentage integer. `fare_amount` equals `platform_fee_amount + driver_payout_amount`.
- `DeltaConfig` (in `schemas/lakehouse/config/`) operates via raw SQL `ALTER TABLE` rather than through Python Delta Lake APIs, requiring an active `SparkSession` to be passed in. It is not automatically applied at table creation — a separate `enable_delta_features.py` script must be run against existing tables.
- The `schemas/lakehouse/` sub-package has its own `pyproject.toml`, `venv`, and mypy configuration. It is a standalone installable package separate from the main simulation or bronze-ingestion venvs.

## Related Modules

- [schemas/lakehouse](lakehouse/CONTEXT.md) — Shares Kafka & Event Streaming domain (dlq schema)
