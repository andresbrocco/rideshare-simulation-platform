# CONTEXT.md — Api

## Purpose

FastAPI application layer that exposes the SimPy simulation engine over HTTP and WebSocket. Responsible for lifecycle control (start/pause/resume/stop/reset), real-time state streaming to connected frontends, agent management, and observable metrics collection. Acts as the bridge between the synchronous SimPy event loop (running in a background thread) and async HTTP/WebSocket clients.

## Responsibility Boundaries

- **Owns**: HTTP route definitions, WebSocket connection management, Redis pub/sub fan-out to WebSocket clients, per-request rate limiting, API key authentication, security headers middleware, state snapshots for client reconnection, periodic metrics push to OTel
- **Delegates to**: `engine` (all simulation state mutations), `redis_subscriber` (pub/sub listen loop), `snapshots` (assembling full-state payloads from engine internals), `metrics` (OTel counter/gauge updates)
- **Does not handle**: Kafka publishing, agent DNA generation, geospatial matching, trip lifecycle — those live in `engine` and `agents`

## Key Concepts

- **Dual real-time channels**: New events from the simulation travel via Redis pub/sub (`driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`) and are fanned out to WebSocket clients by `RedisSubscriber`. Separately, a `StatusBroadcaster` pushes a full simulation status summary every second. These serve different purposes: Redis events carry entity-level deltas; status broadcasts carry aggregate counters.
- **WebSocket authentication**: Browsers cannot send custom HTTP headers during a WebSocket upgrade. Authentication is conveyed via `Sec-WebSocket-Protocol: apikey.<key>`. The server echoes the subprotocol back on accept to satisfy the browser handshake. `WebSocketRateLimiter` applies a separate sliding-window limit (5 connections per 60 s) keyed by API key.
- **StateSnapshotManager**: Reads directly from the engine's in-memory `_active_drivers` / `_active_riders` / `_matching_server` registries to assemble a full-state snapshot. Used on WebSocket connect so a new client immediately sees current map state without waiting for the next delta event.
- **Thread boundary**: The SimPy engine runs in a background thread. Routes that call `engine.start()`, `engine.pause()`, etc. cross a thread boundary; the engine stores an `asyncio` event loop reference set during lifespan startup so it can post callbacks back to the async context.
- **MetricsUpdater**: Bridges SimPy internal state (queried synchronously) to the OTel push-based exporter. Runs every 4 s to match the OTel export cadence. It gathers live counts directly from engine internals rather than relying on in-flight Kafka events.
- **Event transformation**: `RedisSubscriber._transform_event` maps backend event formats to frontend-expected WebSocket message formats. GPS ping events (identified by `entity_type` field) become `gps_ping` messages; profile events (`driver.*`) deliberately omit the `status` field to avoid overwriting the frontend's current driver status. Rider `idle` status is remapped to `requesting` for frontend compatibility.

## Non-Obvious Details

- `app.state.engine` and `app.state.simulation_engine` are the same object — the duplicate key exists for backward compatibility after a rename.
- `/health` is intentionally unauthenticated so infrastructure probes (Kubernetes, load balancers) can reach it without credentials.
- Rate limiting uses `slowapi` with a custom key function that identifies clients by API key first, then falls back to IP. The `RateLimitExceeded` handler is wired manually (not via `SlowAPIMiddleware`) because `SlowAPIMiddleware` combined with FastAPI's decorator approach causes 500 responses on successful requests.
- `RedisSubscriber.start()` waits up to 10 s for the pub/sub subscription to be confirmed before releasing the lifespan, ensuring no events are missed during startup.
- Stream processor health is polled via an internal Docker network URL (`http://stream-processor:8080/health`) — this will fail outside Docker. It is treated as optional and does not affect the overall health aggregate.
- `ACTIVE_TRIP_STATES` in `snapshots.py` controls which trips appear as map routes on client reconnect. Terminal trip states (`COMPLETED`, `CANCELLED`) are excluded deliberately.

## Related Modules

- [schemas/api](../../../../schemas/api/CONTEXT.md) — Reverse dependency — Provides openapi.json
- [services/simulation/scripts](../../scripts/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
