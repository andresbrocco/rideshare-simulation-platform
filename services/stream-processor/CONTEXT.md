# CONTEXT.md — Stream Processor

## Purpose

Bridges Kafka simulation events to Redis for real-time consumption by the frontend WebSocket layer. It consumes from six Kafka topics, routes each message to a per-topic handler, and publishes results to Redis pub/sub channels. GPS events receive windowed aggregation to reduce volume before being forwarded; all other topics are passed through immediately.

## Responsibility Boundaries

- **Owns**: Kafka consumption, per-topic routing, GPS windowed aggregation, Redis pub/sub publishing, event deduplication
- **Delegates to**: Handlers (topic-specific parsing and transformation), `RedisSink` (batched publish with latency tracking), OpenTelemetry Collector (traces and metrics export)
- **Does not handle**: Kafka topic creation by the simulation (stream-processor pre-creates topics at startup to avoid partition assignment delays), long-term storage (that is Bronze Ingestion's responsibility), WebSocket connections (the simulation service owns those)

## Key Concepts

**Windowed GPS Aggregation**: GPS pings arrive at high frequency from the simulation. The processor batches them over a configurable time window (`PROCESSOR_WINDOW_SIZE_MS`, default 100ms) and reduces them using one of two strategies: `latest` (keep only the most recent ping per driver) or `sample` (emit every Nth message). All other event types bypass windowing and publish immediately on receipt.

**Two-Thread Architecture**: The main Kafka poll loop runs on the main thread. A FastAPI/Uvicorn HTTP server for health checks and metrics runs on a daemon background thread (`api-server`). These communicate only through the thread-safe `MetricsCollector` singleton — there is no shared mutable state outside of it.

**Deduplication via Redis SET NX**: The `EventDeduplicator` uses `SET NX EX` on `event:processed:<event_id>` keys with a 1-hour TTL. This is atomic — a single Redis round-trip both checks and marks an event as seen. This guards against at-least-once Kafka redelivery without requiring a separate lookup.

**Manual Offset Commits**: `enable.auto.commit` is `False`. Offsets are committed either after every `batch_commit_size` (100) processed-and-published messages, or on a time-based interval (`commit_interval_sec`, default 5s), whichever comes first. This prevents consumer lag from growing stale while still batching commits.

**Handler Toggle Flags**: GPS, trips, driver status, and surge handlers can be disabled independently via `PROCESSOR_*_ENABLED` env vars. Profile and rating handlers are always enabled (they are required for real-time agent visibility and cannot be toggled off).

## Non-Obvious Details

- The `produced_at` timestamp from each Kafka event is re-injected into the result dict after handler processing so that `RedisSink` can measure end-to-end latency from Kafka production to Redis publish.
- Topic pre-creation at startup avoids a race condition where the consumer would hang waiting for partition assignments if topics don't yet exist (the simulation creates them only after its first event). Up to 30 warmup poll iterations are attempted before proceeding.
- `KafkaSettings` has a `model_validator` that raises if `KAFKA_SASL_USERNAME` or `KAFKA_SASL_PASSWORD` are empty, even when `security_protocol` is `PLAINTEXT`. In local development this means credentials must always be provided (even as dummy values).
- The `MetricsCollector` uses rolling deque windows for rate calculation. Rates are computed over `min(window_seconds, elapsed)` to avoid inflated rates during the warm-up period immediately after startup.
- `prometheus_exporter` is imported lazily inside `MetricsCollector` methods (not at the module top level) to prevent circular import issues at initialization time.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/grafana/dashboards/monitoring](../grafana/dashboards/monitoring/CONTEXT.md) — Reverse dependency — Provides simulation-metrics.json
- [services/prometheus/rules](../prometheus/rules/CONTEXT.md) — Reverse dependency — Provides rideshare:infrastructure:headroom, rideshare:performance:kafka_lag_headroom, rideshare:performance:simpy_queue_headroom (+9 more)
- [services/stream-processor/tests](tests/CONTEXT.md) — Shares Redis and Real-Time State domain (redis set nx deduplication)
