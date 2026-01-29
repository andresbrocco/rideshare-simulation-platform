# CONTEXT.md — Redis Client

## Purpose

Manages Redis integration for state snapshots and event filtering. State snapshots enable WebSocket clients to recover simulation state on reconnection without replaying the full simulation. The publishing layer has been **deprecated** in favor of the stream processor service consuming from Kafka.

## Responsibility Boundaries

- **Owns**: State snapshot storage and retrieval with TTL management, event filtering logic for visualization
- **Delegates to**: Stream processor service (services/stream-processor/) for pub/sub publishing from Kafka
- **Does not handle**: Direct event publishing to Redis pub/sub (now handled by stream processor)

## Key Concepts

**State Snapshots**: Ephemeral cache of driver/trip/surge state stored with 30-minute TTL. Enables frontend reconnection without full simulation replay. Keys follow pattern `snapshot:{entity_type}:{entity_id}`.

**EventFilter**: Determines which Kafka events should trigger Redis updates (filters out offer lifecycle noise) and transforms domain events into visualization-optimized messages.

## Non-Obvious Details

The module contains a **deprecated RedisPublisher** class that was part of the old dual-publishing architecture. The simulation now publishes exclusively to Kafka, and the separate stream processor service consumes those events and publishes to Redis pub/sub. RedisPublisher remains for backward compatibility but is no longer used in the main event flow (see `event_emitter.py` docstring).

StateSnapshotManager uses async Redis client while RedisPublisher uses sync Redis client. This reflects their different usage contexts: snapshots are accessed from async API handlers, while the deprecated publisher was designed to work from SimPy processes.

## Related Modules

- **[services/stream-processor/src/handlers](../../../stream-processor/src/handlers/CONTEXT.md)** — Replaces deprecated RedisPublisher; consumes from Kafka and publishes to Redis pub/sub
- **[services/simulation/src/api/routes](../api/routes/CONTEXT.md)** — Uses StateSnapshotManager for WebSocket state recovery on client reconnection
- **[services/frontend/src](../../../frontend/src/CONTEXT.md)** — Consumes snapshots via WebSocket for initial state hydration
