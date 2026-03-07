# CONTEXT.md — Kafka

## Purpose

Provides the simulation's Kafka publishing layer: a tuned producer, per-topic serializers with JSON Schema validation, a schema registry client, topic-aware partition key extraction, and intentional data corruption for testing the Bronze layer's dead-letter queue (DLQ) handling.

## Responsibility Boundaries

- **Owns**: Kafka message production, event serialization, schema registration and caching, partition key strategy, and controlled corruption injection
- **Delegates to**: `core.correlation` for trace correlation IDs; `metrics.prometheus_exporter` for corruption counters; `schemas/kafka/` directory for JSON Schema files
- **Does not handle**: Consumer logic, topic creation, Kafka cluster configuration, or downstream routing

## Key Concepts

- **Additive corruption**: When corruption fires, a second corrupted copy of the event is published alongside the clean event. The clean event is never replaced or withheld. The corrupted copy receives a new `event_id` prefixed `corrupted-<uuid>` so the stream processor's Redis dedup check treats it as a distinct message.
- **SerializerRegistry**: Singleton with lazy initialization per topic. If Schema Registry is unreachable at startup, the registry is disabled and events are published without schema validation — this is intentional graceful degradation, not an error.
- **`MALFORMED_EVENT_RATE`**: Environment variable (float 0.0–1.0) that controls the per-event probability of injecting a corrupted copy. Defaults to `0.0` (disabled). Set via the performance controller or manually for DLQ testing.

## Non-Obvious Details

- **`linger.ms` is 80ms by design**: The stream processor aggregation window is 100ms. Keeping `linger.ms` below that window ensures batches arrive before the processor flushes, avoiding empty windows.
- **GPS span sampling at 1%**: GPS pings fire roughly 1,200 times per trip. Tracing every one creates disproportionate OpenTelemetry overhead, so only 1% receive a full span. Non-GPS topics are always traced.
- **BufferError handling drops messages**: If the producer queue is full after one retry poll, the message is silently dropped and logged as a warning rather than raising an exception. This prevents crashing the SimPy event loop at the cost of possible message loss under extreme backpressure.
- **`critical=True` flushes synchronously**: Passing `critical=True` to `produce()` triggers a 5-second blocking flush. Use only for lifecycle events (e.g., session start/stop) where delivery confirmation matters more than throughput.
- **Schema validation is non-fatal in `serialize_for_kafka`**: Validation failure logs a warning and continues. This avoids halting the simulation if the Schema Registry returns a stale or incompatible schema version.
- **Poll batching**: `poll(0)` is called every 10 non-critical produces to drain the delivery callback queue, reducing Python-to-librdkafka round-trips without blocking.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
