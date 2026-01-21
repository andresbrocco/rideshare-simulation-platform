# CONTEXT.md — Kafka

## Purpose

Event publishing abstraction for streaming simulation events to Kafka with schema validation, partitioning strategy, and controlled data corruption for testing downstream DLQ handling.

## Responsibility Boundaries

- **Owns**: Event serialization, schema registration and validation, partition key extraction, idempotent message delivery, controlled data corruption for DLQ testing
- **Delegates to**: Confluent Kafka client for broker communication, Schema Registry for schema storage, downstream consumers for event processing
- **Does not handle**: Event consumption, topic creation/management, consumer group coordination, downstream event processing logic

## Key Concepts

**Reliability Tiers**: Events classified as critical (trips, payments) flush synchronously with 5s timeout; high-volume events (GPS pings, status) use fire-and-forget with error logging. Producer configured for idempotence with acks=all, retries=5, and exactly-once semantics.

**Graceful Degradation**: If schema validation fails, events are published as raw JSON with warning logs rather than dropped. SerializerRegistry can be disabled to bypass schema validation entirely when Schema Registry is unavailable.

**Partitioning Strategy**: Each topic uses a specific field as partition key to guarantee ordering (trips by trip_id, gps-pings by entity_id, driver-status by driver_id, surge-updates by zone_id). Partition key is extracted from message payload via PARTITION_KEY_MAPPING.

**Data Corruption**: Optional malformed event injection via MALFORMED_EVENT_RATE environment variable. Supports 9 corruption types weighted by severity (schema violations 60%, format violations 40%) to test Bronze layer DLQ handling. Corruption types include missing fields, wrong data types, invalid enums, malformed JSON, truncated payloads.

## Non-Obvious Details

SerializerRegistry is a singleton with lazy initialization—serializers are created on first topic access rather than at startup. This avoids failing fast if Schema Registry is temporarily unavailable.

KafkaProducer handles BufferError by polling to clear queue and retrying once. Failed deliveries are tracked internally in _failed_deliveries list but not retried—consumers are expected to handle missing events via eventual consistency patterns.

The serialize_for_kafka method returns a tuple of (json_string, is_corrupted) to allow producers to log corruption events separately from delivery failures.
