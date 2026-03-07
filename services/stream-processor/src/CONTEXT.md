# CONTEXT.md — Stream Processor src

## Purpose

Core implementation package for the stream processor service. Consumes multiple Kafka topics, applies per-topic processing (windowed aggregation or pass-through), deduplicates events, and publishes results to Redis pub/sub channels for real-time WebSocket fan-out to the frontend.

## Responsibility Boundaries

- **Owns**: Kafka consumer lifecycle, per-topic message routing, GPS windowed aggregation, Redis deduplication, offset commit management, OTel metric emission, HTTP health/metrics API
- **Delegates to**: `handlers/` subdirectory for per-topic event transformation logic; `sinks/` subdirectory for Redis publish mechanics
- **Does not handle**: WebSocket delivery to clients (Control Panel service), Bronze lakehouse ingestion (Bronze Ingestion service), Kafka schema validation (Schema Registry)

## Key Concepts

**Windowed vs. pass-through handlers**: GPS pings are aggregated in configurable time windows (default 100ms) using either `latest` (keep only most recent ping per driver per window) or `sample` (emit 1-in-N) strategies. All other topics (trips, driver_status, surge, profiles, ratings) use pass-through handlers that emit results immediately on each message. Windowed handlers are flushed on a timer in the main poll loop.

**Redis deduplication**: `EventDeduplicator` uses atomic Redis `SET NX` with a 1-hour TTL to idempotently skip replayed events. This guards against Kafka at-least-once redelivery. Dedup operates on `event_id` before the message reaches a handler.

**Manual offset commits**: `enable_auto_commit` is `False` by default. Offsets are committed either when a batch of N messages is published (`batch_commit_size`, default 100) or when `commit_interval_sec` (default 5s) elapses — whichever occurs first. This prevents stale consumer lag reporting.

**Two-layer metrics**: `MetricsCollector` maintains an in-process rolling-window snapshot (60s) for the `/metrics` HTTP endpoint. `prometheus_exporter` wraps OTel instruments (counters, histograms, observable gauges) that export via OTLP gRPC to the OTel Collector. The `get_snapshot()` call on MetricsCollector synchronizes gauge values into the OTel exporter's snapshot dict.

**HTTP API in daemon thread**: FastAPI/uvicorn runs in a background daemon thread alongside the main synchronous Kafka poll loop. The health endpoint reflects live Kafka and Redis connectivity; the `/metrics` endpoint returns rolling-window throughput and latency stats.

## Non-Obvious Details

- `produced_at` is stripped from events by handlers (which may transform or aggregate), then re-injected from the original Kafka message payload into handler results before publishing to Redis. This preserves end-to-end latency measurement (`stream_processor_pipeline_latency_seconds`).
- On startup, `ensure_topics_exist()` pre-creates all required Kafka topics via AdminClient before the consumer subscribes. Without this, the consumer may fail to get partition assignments if it subscribes before the simulation has published anything.
- The consumer warmup loop polls for up to 30 seconds waiting for partition assignment before setting `self.running = True`. Health check callbacks only reflect `running` state, so the service reports unhealthy during this warmup window.
- `KafkaSettings` validator raises `ValueError` if `KAFKA_SASL_USERNAME` or `KAFKA_SASL_PASSWORD` are empty, even in PLAINTEXT mode. The validator runs unconditionally.
- GPS aggregation ratio metrics are tracked as deltas between window flushes (not cumulative totals) to report per-window reduction rates correctly.
- Observable gauges in OTel use a thread-safe dict (`_snapshot_values`) rather than direct callbacks into MetricsCollector to avoid lock contention between the OTel exporter thread and the main poll loop.

## Related Modules

- [services/simulation/src/metrics](../../simulation/src/metrics/CONTEXT.md) — Shares Observability and Metrics domain (metricscollector)
- [services/stream-processor/src/handlers](handlers/CONTEXT.md) — Dependency — Event-type-specific Kafka message processors that validate, route, and optionall...
- [services/stream-processor/src/handlers](handlers/CONTEXT.md) — Shares Redis and Real-Time State domain (pass-through handler, windowed handler)
