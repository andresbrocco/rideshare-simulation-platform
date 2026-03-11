# CONTEXT.md — tests/api

## Purpose

Unit tests for the simulation service's FastAPI layer, covering authentication (static admin key and session-based), role enforcement (viewer vs. admin), session store, user store, rate limiting, simulation lifecycle control, agent spawning, puppet agent actions, controller mode, metrics endpoints, WebSocket connections, and the Redis-to-WebSocket fanout pipeline. All tests run without a real engine or external services by mocking at the module level.

## Responsibility Boundaries

- **Owns**: Contract verification for all HTTP and WebSocket endpoints; role-based access control enforcement (viewer vs. admin); session lifecycle (create/get/delete via Redis); user store (bcrypt-hashed passwords, singleton); rate limit policy enforcement; Redis subscriber message transformation and fanout behavior
- **Delegates to**: `conftest.py` for shared fixtures (`test_client`, `auth_headers`, `mock_simulation_engine`, `mock_redis_client`, `mock_matching_server`); individual test files for fixture extensions specific to their domain
- **Does not handle**: Integration-level behavior (no real SimPy engine, Redis, or Kafka); end-to-end flow across services

## Key Concepts

**Engine module mocking via `sys.modules`**: The `mock_engine_modules` fixture in `conftest.py` is `autouse=True` and patches `sys.modules["engine"]` directly before each test. This prevents the heavyweight SimPy engine from importing, which would fail without a running simulation environment. After each test, the fixture restores the original module references and clears `api.*` entries so the next test reimports cleanly.

**Rate limiter state isolation**: `test_rate_limiting.py` adds a second `autouse=True` fixture (`_fresh_rate_limiter`) that purges all `api.*` module entries from `sys.modules` before and after each test. Because `slowapi` stores counters on the `Limiter` instance (a module-level singleton), forcing a fresh import for every test prevents rate limit counts from bleeding across tests.

**WebSocket API key transport**: WebSocket authentication uses the `Sec-WebSocket-Protocol` header with the value `apikey.<key>`, not the `X-API-Key` header used by REST endpoints. The `extract_api_key` helper in `api.websocket` parses a comma-separated protocol list and finds the `apikey.` prefixed entry. Both static keys and `sess_`-prefixed session keys are accepted.

**Session key authentication path**: Keys with a `sess_` prefix bypass the static key check and trigger a Redis hash lookup at `session:<key>`. The `mock_redis_client` fixture defaults `hgetall` to return `{}` so session lookups fail unless a test explicitly overrides the return value. This prevents accidental session-auth success in tests that only intend to exercise the static key path.

**Role-based access control**: `test_role_enforcement.py` uses `app.dependency_overrides[verify_api_key]` to inject a fixed `AuthContext` (role `viewer` or `admin`) without touching Redis. It clears all `api.*` entries from `sys.modules` before building each app so each fixture gets a pristine import. Viewer role receives HTTP 403 with `{"detail": "Admin role required"}` on simulation control, agent creation, puppet actions, and controller mode endpoints.

**AuthContext**: A frozen dataclass in `api.auth` carrying `role` (literal `"admin"` or `"viewer"`) and `email`. Static key auth always produces `role="admin"`; session key auth reflects the values stored in the Redis hash.

**UserStore**: A module-level singleton (`get_user_store()`) backed by a dict. Passwords are stored as bcrypt hashes (prefix `$2b$`). `test_user_store.py` resets the singleton via `user_store_module._user_store = None` in an `autouse` fixture to prevent cross-test pollution.

**SessionData**: A frozen Pydantic model (`api.session_store`) with fields `api_key`, `email`, `role`, and `expires_at`. `create_session` writes it as a Redis hash under `session:<key>` with a TTL (default 86 400 s / 24 h). `get_session` skips the Redis round-trip entirely for keys without the `sess_` prefix.

## Non-Obvious Details

- `test_redis_fanout.py` and `test_redis_subscriber.py` both test `RedisSubscriber` but from different angles: fanout tests exercise the full async pubsub lifecycle with `asyncio.sleep`-based timing, while subscriber tests call `_transform_event` directly as a unit-testable method. The fanout file imports via `api.redis_subscriber`; the subscriber file imports via `src.api.redis_subscriber` — both resolve to the same class but use different import path conventions.
- The `test_client` fixture in `conftest.py` passes `raise_server_exceptions=False` to `TestClient`, meaning 5xx errors surface as HTTP responses rather than exceptions. Tests that expect 4xx must assert `response.status_code` explicitly.
- Metrics cache expiry is tested by patching `time.time` at the module level inside `api.routes.metrics`, and the test clears `metrics._metrics_cache` directly to ensure a known starting state.
- Driver spawn defaults to `immediate=True` (goes online at once); rider spawn defaults to `immediate=False` (follows DNA-scheduled timing). These defaults are validated in `test_agent_creation.py` and reflect production behavior.
- `mock_simulation_engine._active_drivers` and `_active_riders` are dicts (not lists). The engine mock also exposes `current_time` (callable returning `None`) and `_env.now` (float `0.0`). Tests that previously assumed list-based agent collections will fail if they try to iterate by index.
- `mock_matching_server` exposes `get_active_trips` (returns `[]`) and `_surge_calculator` (set to `None`) in addition to `get_trip_stats` and `get_matching_stats`. These are required by metrics-route code that inspects in-flight trip state.
- `test_auth_login.py` uses a local `auth_test_client` fixture (not `test_client`) that patches `api.routes.auth.get_user_store` and `api.routes.auth.create_session` so the login endpoint can be exercised without a real bcrypt round-trip or Redis write.
