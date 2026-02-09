# CONTEXT.md — Schema Registry

## Purpose

Avro schema management service for the rideshare simulation platform's Kafka topics. Confluent Schema Registry stores, validates, and enforces compatibility for message schemas, ensuring that producers and consumers agree on data formats as schemas evolve over time.

## Responsibility Boundaries

- **Owns**: Schema storage and versioning, compatibility checking (backward/forward/full), schema evolution enforcement, schema ID assignment for serialized messages
- **Delegates to**: Kafka for internal storage (`_schemas` topic), simulation and stream-processor services for schema registration and lookup, producers/consumers for actual message serialization/deserialization
- **Does not handle**: Message serialization (done by Avro serializers in producers/consumers), topic management (Kafka broker), message routing, data transformation

## Key Concepts

**Lazy Schema Registration**: Schemas are not pre-loaded at startup. They are registered automatically when a producer first serializes a message to a topic. This means Schema Registry subjects only appear after the simulation service starts producing events.

**Internal Kafka Storage**: Schema Registry persists all schemas in a Kafka topic called `_schemas`. This means schema data survives Schema Registry restarts as long as the Kafka broker retains the topic. No external database is needed.

**Environment-Variable Configuration**: All Schema Registry settings are configured via environment variables in `compose.yml`. There are no configuration files in this directory — it exists as a documentation anchor in the service tree.

**Small Heap Size**: The JVM heap is set to 128m-256m (`SCHEMA_REGISTRY_HEAP_OPTS: -Xms128m -Xmx256m`) because the rideshare platform has only approximately 8 schemas. The default heap would be unnecessarily large.

## Non-Obvious Details

Schema Registry depends on `kafka-init` completing successfully (via `condition: service_completed_successfully` in compose.yml). This ensures that the Kafka broker is healthy and topics are created before Schema Registry attempts to connect and create its internal `_schemas` topic.

The host port is mapped as `8085:8081` to avoid conflicts. Internal services reference Schema Registry at `http://schema-registry:8081`, while external access from the host uses port `8085`.

## Related Modules

- **[services/kafka](../kafka/CONTEXT.md)** — Provides the broker that Schema Registry connects to and stores schemas in
- **[services/simulation](../simulation/CONTEXT.md)** — Primary schema producer; registers schemas when serializing simulation events
- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Schema consumer; looks up schemas when deserializing events from Kafka
- **[schemas/kafka](../../schemas/kafka/CONTEXT.md)** — Avro schema definitions (.avsc files) used by producers and consumers
- **[infrastructure/docker](../../infrastructure/docker/CONTEXT.md)** — Deployment orchestration; defines Schema Registry service, env vars, and core profile
