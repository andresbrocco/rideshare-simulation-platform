# CONTEXT.md — tests/kafka

## Purpose

Unit tests for the simulation service's Kafka layer, covering event serialization contracts, schema registry integration, producer reliability behaviors, and intentional data corruption injection. These tests run fully in-process with mocked Confluent Kafka internals — no broker or Schema Registry is required.

## Responsibility Boundaries

- **Owns**: Behavioral specification for `KafkaProducer`, `SerializerRegistry`, `SchemaRegistry`, all typed event serializers, and `DataCorruptor`
- **Delegates to**: `schemas/kafka/` for JSON Schema fixtures loaded from disk in `test_json_schemas.py` and `test_event_serialization.py`
- **Does not handle**: Integration tests against a live broker, consumer behavior, or topic management

## Key Concepts

- **Critical vs non-critical produce**: `KafkaProducer.produce()` accepts a `critical=True` flag. Critical produces call `flush(timeout=5.0)` before returning; non-critical produces use a batched `poll(0)` every `_POLL_BATCH_SIZE` calls to reduce Python→C round-trips into librdkafka. Tests in `TestBatchedPoll` and `TestGpsSpanSampling` specify this behavior precisely.
- **GPS span sampling**: GPS pings fire at high frequency (~1,200 per trip). The producer samples OTel spans at `_GPS_SPAN_SAMPLE_RATE` (1%) for the `gps_pings` topic only. All other topics are always traced.
- **SerializerRegistry singleton reset**: Because `SerializerRegistry` is a singleton, the `reset_registry` autouse fixture in `test_serializer_registry.py` calls `SerializerRegistry.reset()` before and after every test to prevent state leakage between tests.
- **Lazy schema loading**: Serializers read JSON schema files from disk during `serialize()`, not during `__init__()`. This means `SerializerRegistry.get_serializer()` succeeds even when schema files are absent; failure is deferred to first use.
- **dual-payload serialization**: `EventSerializer.serialize_for_kafka()` returns a 3-tuple `(clean_json, corrupted_json, corruption_type)`. When `DataCorruptor` does not fire, `corrupted_json` and `corruption_type` are `None`. When corruption fires, both the intact model payload and a separately mutated payload are returned — the producer publishes both to allow downstream DLQ testing.
- **DataCorruptor**: Probabilistically injects malformed events controlled by the `MALFORMED_EVENT_RATE` env var. Supports multiple `CorruptionType` variants (empty payload, malformed JSON, truncated message, missing required field, wrong data type, invalid enum, invalid UUID, invalid timestamp, out-of-range value). Corrupted copies always replace `event_id` with a `corrupted-` prefix and never mutate the original dict.

## Non-Obvious Details

- `test_event_serialization.py` imports from both `kafka.serialization` (bare module) and `src.kafka.serialization` (prefixed), reflecting dual import path support in the simulation package.
- `test_json_schemas.py` loads schemas by traversing five parent directories from the test file location (`Path(__file__).parent.parent.parent.parent.parent / "schemas" / "kafka"`), reaching the repo-level `schemas/kafka/` directory. Any test environment path change that breaks this relative chain causes silent `FileNotFoundError`.
- The `TestKafkaProducerReliability` class documents a known gap (`ERROR-001`) where events would previously be silently dropped on delivery failure with no retry. Tests specify the required `_failed_deliveries` tracking list and `BufferError` retry behavior.
- Schema caching in `SchemaRegistry.get_schema()` is verified to call the underlying client exactly once for repeated lookups (identity cache).

## Related Modules

- [schemas/kafka](../../../../schemas/kafka/CONTEXT.md) — Dependency — Formal JSON Schema contracts for all Kafka event topics in the rideshare simulat...
