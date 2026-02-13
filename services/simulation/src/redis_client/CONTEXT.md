# CONTEXT.md — Redis Client

## Purpose

Manages Redis integration for state snapshots, event filtering, and pub/sub publishing. State snapshots enable WebSocket clients to recover simulation state on reconnection without replaying the full simulation. RedisPublisher provides direct Redis pub/sub publishing and is actively used alongside the stream processor service.

## Responsibility Boundaries

- **Owns**: State snapshot storage and retrieval with TTL management, event filtering logic for visualization
- **Delegates to**: Stream processor service (services/stream-processor/) for pub/sub publishing from Kafka
- **Does not handle**: Kafka event consumption (handled by stream processor)

## Key Concepts

**State Snapshots**: Ephemeral cache of driver/trip/surge state stored with 30-minute TTL. Enables frontend reconnection without full simulation replay. Keys follow pattern `snapshot:{entity_type}:{entity_id}`.

**EventFilter**: Determines which Kafka events should trigger Redis updates (filters out offer lifecycle noise) and transforms domain events into visualization-optimized messages.

## Non-Obvious Details

The module contains a **RedisPublisher** class that is actively instantiated in `main.py` and passed to MatchingServer, SurgePricingCalculator, and SimulationEngine. It provides direct Redis pub/sub publishing alongside the stream processor service which consumes from Kafka and also publishes to Redis.

StateSnapshotManager uses async Redis client while RedisPublisher uses sync Redis client. This reflects their different usage contexts: snapshots are accessed from async API handlers, while RedisPublisher was designed to work from SimPy processes.

## Related Modules

- **[services/stream-processor/src](../../../stream-processor/src/CONTEXT.md)** — Also publishes to Redis pub/sub channels after consuming from Kafka; provides alternative event delivery path
- **[src/agents](../agents/CONTEXT.md)** — Agents emit events that flow through Redis for frontend delivery; state snapshots cache agent positions
- **[services/frontend/src/components](../../../frontend/src/components/CONTEXT.md)** — Frontend consumes Redis pub/sub messages via WebSocket for real-time visualization updates
