# CONTEXT.md — Stream Processor

## Purpose

Bridges Kafka event streams with Redis pub/sub for real-time frontend visualization. Consumes events from multiple Kafka topics, aggregates high-volume GPS data, deduplicates events, and publishes to Redis channels for WebSocket fanout.

## Responsibility Boundaries

- **Owns**: Kafka-to-Redis translation, GPS ping aggregation, event deduplication, per-topic routing logic
- **Delegates to**: Kafka for durable event storage, Redis for pub/sub delivery, simulation service for event generation, frontend for WebSocket subscriptions
- **Does not handle**: Event generation, WebSocket connections, data persistence, business logic

## Key Concepts

**Handler Pattern**: Two types of handlers process different event streams:
- Pass-through handlers (trips, driver-status, surge, profiles) immediately publish to Redis
- Windowed handlers (GPS) buffer events and emit aggregated results on flush

**Windowed Aggregation**: GPS pings are aggregated within time windows (default 100ms) to reduce message volume to frontend. Two strategies available:
- "latest": Keep only the most recent position per entity
- "sample": Emit every Nth message per entity

**Event Deduplication**: Uses Redis SET NX to atomically track processed event IDs within a TTL window (1 hour), preventing duplicate processing if Kafka messages are redelivered.

**Topic-to-Channel Routing**: Maps Kafka topics to Redis pub/sub channels:
- gps-pings → driver-updates / rider-updates (based on entity_type)
- trips → trip-updates
- driver-status → driver-updates
- surge-updates → surge-updates
- driver-profiles → driver-updates
- rider-profiles → rider-updates

## Non-Obvious Details

**Consumer Warmup**: The processor polls until partition assignment is complete before reporting healthy. This prevents health checks from passing before the consumer is ready to receive messages.

**Manual Offset Commits**: Auto-commit is disabled by default. Offsets are committed in batches after successful Redis publish to ensure at-least-once delivery semantics.

**Topic Pre-creation**: The processor creates missing Kafka topics on startup (1 partition, replication factor 1) to avoid waiting for the simulation producer to auto-create them.

**Graceful Shutdown**: On SIGTERM/SIGINT, the processor flushes windowed state, commits pending offsets, and closes connections before exiting.

**Metrics Collection**: Tracks throughput rates, GPS aggregation ratio, Redis publish latency, and connection health. Exposed via HTTP API at `/health` and `/metrics` endpoints.

## Related Modules

- **[services/simulation](../simulation/CONTEXT.md)** — Event source; simulation publishes to Kafka topics that stream-processor consumes
- **[services/frontend](../frontend/CONTEXT.md)** — Event destination; frontend WebSocket subscribes to Redis channels that stream-processor publishes to
- **[schemas/kafka](../../schemas/kafka/CONTEXT.md)** — Event schema contract; stream-processor validates and transforms events based on these definitions
