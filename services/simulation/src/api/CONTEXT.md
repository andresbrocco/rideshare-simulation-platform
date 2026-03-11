# CONTEXT.md — Api

## Purpose

FastAPI application layer that exposes the SimPy simulation engine over HTTP and WebSocket. Responsible for lifecycle control (start/pause/resume/stop/reset), real-time state streaming to connected frontends, agent management, and observable metrics collection. Acts as the bridge between the synchronous SimPy event loop (running in a background thread) and async HTTP/WebSocket clients.

## Responsibility Boundaries

- **Owns**: HTTP route definitions, WebSocket connection management, Redis pub/sub fan-out to WebSocket clients, per-request rate limiting, API key authentication (static admin key + session keys), role-based access control (`require_admin`), bcrypt-hashed user store (`user_store.py`), security headers middleware, state snapshots for client reconnection, periodic metrics push to OTel, session lifecycle (create/validate/delete via `session_store.py`)
- **Delegates to**: `engine` (all simulation state mutations), `redis_subscriber` (pub/sub listen loop), `snapshots` (assembling full-state payloads from engine internals), `metrics` (OTel counter/gauge updates), `session_store` (Redis-backed session key persistence), `user_store` (bcrypt credential verification)
- **Does not handle**: Kafka publishing, agent DNA generation, geospatial matching, trip lifecycle — those live in `engine` and `agents`

## Key Concepts

- **Dual real-time channels**: New events from the simulation travel via Redis pub/sub (`driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`) and are fanned out to WebSocket clients by `RedisSubscriber`. Separately, a `StatusBroadcaster` pushes a full simulation status summary every second. These serve different purposes: Redis events carry entity-level deltas; status broadcasts carry aggregate counters.
- **Dual authentication paths**: `verify_api_key` accepts two key types. Keys prefixed `sess_` are looked up in Redis via `session_store.get_session` and carry role/email from the stored `SessionData`. All other keys are compared against the static admin key from settings and receive `role="admin"`. This allows provisioned visitor accounts (role `"viewer"`) to authenticate alongside the static admin key without altering existing integrations.
- **AuthContext**: Immutable frozen dataclass (`role`, `email`) returned by `verify_api_key`. Downstream route dependencies receive this instead of a raw string key. The `require_admin` dependency chains off `verify_api_key` and raises HTTP 403 when `role != "admin"`.
- **UserStore and session lifecycle**: `user_store.py` holds an in-memory registry keyed by email with bcrypt-hashed passwords. It is write-only at startup (provisioning); concurrent async reads are safe. `session_store.py` persists session keys as Redis hashes at `session:{api_key}` with TTL-based auto-eviction; `delete_session` provides explicit invalidation for logout.
- **WebSocket authentication**: Browsers cannot send custom HTTP headers during a WebSocket upgrade. Authentication is conveyed via `Sec-WebSocket-Protocol: apikey.<key>`. The server echoes the subprotocol back on accept to satisfy the browser handshake. WebSocket auth now also accepts `sess_` session keys via `_is_valid_key`. `WebSocketRateLimiter` applies a separate sliding-window limit (5 connections per 60 s) keyed by API key.
- **StateSnapshotManager**: Reads directly from the engine's in-memory `_active_drivers` / `_active_riders` / `_matching_server` registries to assemble a full-state snapshot. Used on WebSocket connect so a new client immediately sees current map state without waiting for the next delta event.
- **Thread boundary**: The SimPy engine runs in a background thread. Routes that call `engine.start()`, `engine.pause()`, etc. cross a thread boundary; the engine stores an `asyncio` event loop reference set during lifespan startup so it can post callbacks back to the async context.
- **MetricsUpdater**: Bridges SimPy internal state (queried synchronously) to the OTel push-based exporter. Runs every 4 s to match the OTel export cadence. It gathers live counts directly from engine internals rather than relying on in-flight Kafka events.
- **Event transformation**: `RedisSubscriber._transform_event` maps backend event formats to frontend-expected WebSocket message formats. GPS ping events (identified by `entity_type` field) become `gps_ping` messages; profile events (`driver.*`) deliberately omit the `status` field to avoid overwriting the frontend's current driver status. Rider `idle` status is remapped to `requesting` for frontend compatibility.

## Non-Obvious Details

- `app.state.engine` and `app.state.simulation_engine` are the same object — the duplicate key exists for backward compatibility after a rename.
- `StateSnapshotManager` is initialised eagerly at `create_app` time (before lifespan) so the WebSocket endpoint can use it during testing without waiting for the lifespan context to start. The lifespan then overwrites `app.state.snapshot_manager` with the same type; both point to separate instances but are functionally identical.
- `auth.get_session` is a thin wrapper around `session_store.get_session` that extracts `redis_client` from `request.app.state`. This indirection exists so tests that call `verify_api_key` directly with `request=None` can patch just `api.auth.get_session` rather than constructing a real `Request`.
- Session keys returned by `POST /auth/login` carry a `sess_` prefix. The static admin key (from settings) does not use this prefix and bypasses Redis entirely — it is never stored in or invalidated by the session store.
- `POST /auth/register` provisions `viewer`-role accounts only; admin promotion is not supported through this endpoint. It is called by the Lambda `provision-visitor` orchestrator to register new visitor credentials.
- `/health` is intentionally unauthenticated so infrastructure probes (Kubernetes, load balancers) can reach it without credentials.
- Rate limiting uses `slowapi` with a custom key function that identifies clients by API key first, then falls back to IP. The `RateLimitExceeded` handler is wired manually (not via `SlowAPIMiddleware`) because `SlowAPIMiddleware` combined with FastAPI's decorator approach causes 500 responses on successful requests.
- `RedisSubscriber.start()` waits up to 10 s for the pub/sub subscription to be confirmed before releasing the lifespan, ensuring no events are missed during startup.
- Stream processor health is polled via an internal Docker network URL (`http://stream-processor:8080/health`) — this will fail outside Docker. It is treated as optional and does not affect the overall health aggregate.
- `ACTIVE_TRIP_STATES` in `snapshots.py` controls which trips appear as map routes on client reconnect. Terminal trip states (`COMPLETED`, `CANCELLED`) are excluded deliberately.

## Related Modules

- [services/simulation/src/redis_client](../redis_client/CONTEXT.md) — Shares Checkpointing & State Persistence domain (statesnapshotmanager)
