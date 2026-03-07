# CONTEXT.md — Redis Client

## Purpose

Provides the simulation's real-time visualization pipeline to Redis. Handles event publication to pub/sub channels for live frontend updates and maintains state snapshots that allow newly connected (or reconnected) clients to reconstruct current simulation state without replaying the full event history.

## Responsibility Boundaries

- **Owns**: Redis pub/sub publishing, state snapshot persistence and retrieval, event filtering and transformation from internal domain events to frontend-ready channel messages
- **Delegates to**: `pubsub.channels` for channel name constants and typed message schemas; `events.schemas` for source event types; `metrics` and `core.correlation` for observability
- **Does not handle**: WebSocket fan-out (that is the stream processor's responsibility), Kafka publishing (handled by `src/kafka`), or event sourcing/persistence

## Key Concepts

- **StateSnapshotManager**: Writes compacted per-entity state to Redis keys (`snapshot:drivers:<id>`, `snapshot:trips:<id>`, `snapshot:surge:<zone_id>`) with a 30-minute TTL. Consumed on WebSocket client connect to deliver full current state before live events begin streaming.
- **EventFilter**: Acts as a gate between the internal event bus and the pub/sub layer. Determines which event types are visible to the frontend and transforms domain events to channel-specific typed messages.
- **Channel routing**: Events are routed to one of four channels (`driver_updates`, `rider_updates`, `trip_updates`, `surge_updates`) based on event type and entity type.

## Non-Obvious Details

- **Sync publisher, async snapshot manager**: `RedisPublisher` uses the synchronous `redis.Redis` client intentionally — SimPy processes run in a background thread and cannot use async I/O. `StateSnapshotManager` uses `redis.asyncio` because it is called from FastAPI async route handlers. Both co-exist but are never interchangeable.
- **Trip offer events are suppressed**: `EventFilter.should_publish` explicitly drops `trip.offer_sent`, `trip.offer_expired`, and `trip.offer_rejected` from the pub/sub feed. These are high-frequency internal matching events not meaningful to visualization consumers.
- **GPS ping status inference**: When a `GPSPingEvent` arrives for a driver, the driver's exact status is not embedded in the event. `EventFilter.transform` infers `en_route_pickup` if a `trip_id` is present, otherwise `available`. This is a lossy approximation — drivers actively on a trip may briefly appear as `en_route_pickup` regardless of their actual sub-state.
- **Snapshot stores only the last 10 path points**: `store_driver` trims `recent_path` to the trailing 10 entries to bound Redis memory usage per driver.
- **`publish` is a sync wrapper**: The async `publish` method on `RedisPublisher` simply calls `publish_sync` synchronously; it exists only to satisfy async caller interfaces without actual async I/O.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
