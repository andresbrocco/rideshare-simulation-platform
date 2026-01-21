# CONTEXT.md — Stream Processor

## Purpose

Bridges Kafka event streams to Redis pub/sub channels for real-time frontend visualization. Consumes simulation events from Kafka topics, applies optional aggregation strategies, and publishes to Redis channels that the WebSocket server subscribes to.

## Responsibility Boundaries

- **Owns**: Kafka-to-Redis event routing, GPS ping aggregation, event deduplication, per-topic handler dispatch
- **Delegates to**: Kafka for event sourcing, Redis for pub/sub delivery, simulation service for event production
- **Does not handle**: Event schema validation (accepts invalid events with logging), WebSocket connections (handled by simulation API), frontend state management

## Key Concepts

**Windowed Aggregation**: GPS pings are buffered in time windows (default 100ms) and aggregated before publishing. Two strategies exist: "latest" keeps only the most recent ping per entity, "sample" emits every Nth ping. This reduces message rates from hundreds per second to manageable levels for the frontend.

**Handler Routing**: Each Kafka topic maps to a specific handler (gps-pings → GPSHandler, trips → TripHandler). Handlers are either pass-through (immediate Redis publish) or windowed (buffer and flush on timer). The `is_windowed` property determines flushing behavior.

**Event Deduplication**: Uses Redis SET NX with TTL to track processed event_id values. Atomic operation prevents duplicate processing across restarts or rebalances.

**Manual Offset Commits**: Auto-commit is disabled. Offsets are committed in batches after successful Redis publish to ensure at-least-once delivery semantics.

## Non-Obvious Details

The service runs two concurrent subsystems: a Kafka consumer loop in the main thread and a FastAPI health server in a background thread. Health checks validate both Kafka partition assignment and Redis connectivity.

Topic subscription happens eagerly but partition assignment is asynchronous. The warmup phase polls for up to 30 seconds until the consumer receives partition assignments, ensuring health checks reflect actual readiness.

GPS aggregation state is cleared on each window flush. Metrics track aggregation ratios (messages received / messages emitted) to quantify bandwidth reduction.

Profile events (driver-profiles, rider-profiles) are always enabled regardless of feature flags to ensure real-time agent visibility.
