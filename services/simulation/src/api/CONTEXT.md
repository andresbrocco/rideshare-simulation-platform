# CONTEXT.md — API

## Purpose

FastAPI control panel for the simulation engine. Provides REST endpoints for simulation lifecycle control (start/stop/pause), WebSocket connections for real-time updates, and health monitoring of dependent services (Redis, Kafka, OSRM, stream processor).

## Responsibility Boundaries

- **Owns**: HTTP/WebSocket server, API authentication, simulation command translation, state snapshot aggregation for reconnecting clients, WebSocket connection lifecycle
- **Delegates to**: SimulationEngine (simulation control), RedisSubscriber (pub/sub fan-out), StateSnapshotManager (snapshot building), route handlers (business logic)
- **Does not handle**: Event publishing (handled by simulation engine and stream processor), actual simulation logic (SimPy engine), agent lifecycle beyond command translation

## Key Concepts

**Two-tier architecture**: API server runs FastAPI with async event loop; simulation engine runs SimPy in a background thread. API sets engine's event loop reference for thread-safe async callbacks.

**WebSocket authentication**: API keys encoded in `Sec-WebSocket-Protocol` header as `apikey.<key>` format (required for browser WebSocket API limitations). REST endpoints use standard `X-API-Key` header.

**Event flow separation**: Simulation publishes to Kafka → stream processor consumes and republishes to Redis pub/sub → RedisSubscriber fans out to WebSocket clients. API never publishes events, only consumes from Redis.

**Snapshot on connect**: New WebSocket connections receive full state snapshot (all active drivers/riders/trips/surge) built from engine's in-memory registries, then receive incremental updates via Redis pub/sub.

**Status broadcaster**: Separate async task broadcasts simulation status (uptime, counts, state) to WebSocket clients every 1 second, independent of Redis pub/sub events.

## Non-Obvious Details

**Lifespan management**: Core dependencies (engine, redis_client, agent_factory) are set on app.state immediately during factory call for test compatibility. Background tasks (RedisSubscriber, StatusBroadcaster) start in lifespan context manager.

**Health check tiers**: `/health` is unauthenticated for container orchestration. `/health/detailed` provides latency metrics for Redis, OSRM, Kafka, simulation engine, and stream processor with three-tier status (healthy/degraded/unhealthy based on latency thresholds).

**ACTIVE_TRIP_STATES filter**: StateSnapshotManager only includes trips in specific states (REQUESTED through STARTED) in snapshots to show routes on map. Excludes terminal states (COMPLETED, CANCELLED) and expired offers.

**Event transformation**: RedisSubscriber transforms backend event format to frontend-expected format, including GPS pings vs status changes, coordinate tuple unpacking, and trip state extraction from event_type field.
