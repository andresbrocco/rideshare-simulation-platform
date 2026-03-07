# CONTEXT.md — tests/api

## Purpose

Unit tests for the simulation service's FastAPI layer, covering authentication, rate limiting, simulation lifecycle control, agent spawning, metrics endpoints, WebSocket connections, and the Redis-to-WebSocket fanout pipeline. All tests run without a real engine or external services by mocking at the module level.

## Responsibility Boundaries

- **Owns**: Contract verification for all HTTP and WebSocket endpoints; rate limit policy enforcement; Redis subscriber message transformation and fanout behavior
- **Delegates to**: `conftest.py` for shared fixtures (`test_client`, `auth_headers`, `mock_simulation_engine`); individual test files for fixture extensions specific to their domain
- **Does not handle**: Integration-level behavior (no real SimPy engine, Redis, or Kafka); end-to-end flow across services

## Key Concepts

**Engine module mocking via `sys.modules`**: The `mock_engine_modules` fixture in `conftest.py` is `autouse=True` and patches `sys.modules["engine"]` directly before each test. This prevents the heavyweight SimPy engine from importing, which would fail without a running simulation environment. After each test, the fixture restores the original module references and clears `api.*` entries so the next test reimports cleanly.

**Rate limiter state isolation**: `test_rate_limiting.py` adds a second `autouse=True` fixture (`_fresh_rate_limiter`) that purges all `api.*` module entries from `sys.modules` before and after each test. Because `slowapi` stores counters on the `Limiter` instance (a module-level singleton), forcing a fresh import for every test prevents rate limit counts from bleeding across tests.

**WebSocket API key transport**: WebSocket authentication uses the `Sec-WebSocket-Protocol` header with the value `apikey.<key>`, not the `X-API-Key` header used by REST endpoints. The `extract_api_key` helper in `api.websocket` parses a comma-separated protocol list and finds the `apikey.` prefixed entry.

## Non-Obvious Details

- `test_redis_fanout.py` and `test_redis_subscriber.py` both test `RedisSubscriber` but from different angles: fanout tests exercise the full async pubsub lifecycle with `asyncio.sleep`-based timing, while subscriber tests call `_transform_event` directly as a unit-testable method. The fanout file imports via `api.redis_subscriber`; the subscriber file imports via `src.api.redis_subscriber` — both resolve to the same class but use different import path conventions.
- The `test_client` fixture in `conftest.py` passes `raise_server_exceptions=False` to `TestClient`, meaning 5xx errors surface as HTTP responses rather than exceptions. Tests that expect 4xx must assert `response.status_code` explicitly.
- Metrics cache expiry is tested by patching `time.time` at the module level inside `api.routes.metrics`, and the test clears `metrics._metrics_cache` directly to ensure a known starting state.
- Driver spawn defaults to `immediate=True` (goes online at once); rider spawn defaults to `immediate=False` (follows DNA-scheduled timing). These defaults are validated in `test_agent_creation.py` and reflect production behavior.
