# CONTEXT.md — Kafka Tests

## Purpose

Validates Kafka event publishing layer, including JSON schema validation, schema registry integration, controlled data corruption for DLQ testing, event serialization, and producer reliability features.

## Responsibility Boundaries

- **Owns**: Test coverage for schema validation, serializer registry singleton, data corruption injection, producer delivery tracking, critical event flushing, and BufferError retry logic
- **Delegates to**: Mock Kafka clients for broker simulation, parent conftest for shared fixtures, `src/kafka/` for implementation under test
- **Does not handle**: Integration tests with real Kafka brokers (located in `tests/integration/`), consumer-side testing, topic creation/management tests

## Key Concepts

**Reliability Tier Testing**: `test_producer.py` validates that critical events (trips, payments) trigger synchronous flush with 5s timeout, while non-critical events use async poll(0) for performance. Tests also verify BufferError handling with poll-and-retry pattern.

**Graceful Degradation Validation**: `test_serializer_registry.py` confirms SerializerRegistry can be disabled when Schema Registry is unavailable, and that serializers are created lazily (on first access) to avoid failing fast at startup.

**Data Corruption Scenarios**: `test_data_corruption.py` tests 9 corruption types weighted by severity (schema violations 60%, format violations 40%) to validate Bronze layer DLQ handling. Corruption types include empty payloads, malformed JSON, missing required fields, wrong data types, invalid enums, invalid UUIDs/timestamps, and out-of-range values.

**Schema Validation Coverage**: `test_json_schemas.py` validates all 8 event schemas against JSON Schema spec, ensuring required fields, type constraints, enum values, and common patterns (event_id as UUID, timestamp as ISO8601).

## Non-Obvious Details

`test_schema_registry.py` verifies schema caching behavior—fetching the same schema ID twice should only call the underlying client once. This prevents excessive Schema Registry API calls during high-throughput event production.

`test_serializer_registry.py` tests that missing schema files don't cause initialization failure because serializers only read files during `serialize()`, not during `__init__()`. This lazy file loading enables startup even when Schema Registry is temporarily unavailable.

`test_producer.py` validates that failed deliveries are tracked in `_failed_deliveries` list for observability but are NOT automatically retried—consumers must handle missing events via eventual consistency patterns.

The data corruption system injects topic-aware corruption (e.g., invalid entity_type for gps_pings, out-of-range rating for ratings) rather than generic corruption, ensuring DLQ tests exercise realistic schema violations.

## Related Modules

- **[src/kafka](../../src/kafka/CONTEXT.md)** — Kafka producer implementation under test; tests validate reliability tiers and graceful degradation
- **[tests](../CONTEXT.md)** — Parent test infrastructure providing mock fixtures and test isolation
- **[services/bronze-ingestion](../../../bronze-ingestion/CONTEXT.md)** — Bronze layer that receives corrupted events in DLQ; data corruption tests simulate failure scenarios for ingestion validation
