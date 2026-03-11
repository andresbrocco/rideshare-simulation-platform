# PATTERNS.md

> Observed code patterns in this codebase.

## Error Handling

### Pattern

A typed exception hierarchy under `SimulationError` organizes all errors by recovery intent. The hierarchy has three recovery branches:

- `TransientError` — safe to retry; covers `NetworkError`, `ServiceUnavailableError`, `PersistenceError`
- `PermanentError` — retrying will not help; covers `ValidationError`, `NotFoundError`, `StateError`, `ConfigurationError`
- `FatalError` — requires immediate shutdown

Retry is implemented via `with_retry` (async) and `with_retry_sync` (sync) with exponential backoff (`RetryConfig`: max_attempts=3, base_delay=0.5s, multiplier=2.0, max_delay=30s). Both utilities only catch `TransientError` subclasses by default. Raising `PermanentError` bypasses retry protection silently.

### Locations

- `services/simulation/src/core/exceptions.py` — exception hierarchy definition
- `services/simulation/src/core/retry.py` — `with_retry` and `with_retry_sync` utilities
- `services/simulation/src/geo/osrm_client.py` — `NetworkError` raised on OSRM failures; `NoRouteFoundError` (a `ValidationError`) raised on no-path responses; retried via `with_retry`
- `services/simulation/src/kafka/producer.py` — `BufferError` drops messages with a warning rather than raising, to avoid crashing the SimPy event loop
- `services/simulation/src/db/` — `PersistenceError` raised on SQLite failures; wrapped in savepoint contexts for rollback

### Example

```python
# Only TransientError subclasses trigger retry. PermanentError propagates immediately.
class NetworkError(TransientError): ...
class NoRouteFoundError(ValidationError): ...  # PermanentError — not retried

result = await with_retry(
    operation=lambda: osrm_client.get_route(origin, dest),
    config=RetryConfig(max_attempts=3, base_delay=0.5),
    operation_name="osrm_route_fetch",
)
```

---

## Logging

### Pattern

Structured logging with thread-local context injection and PII masking. Two formatters are supported: `JSONFormatter` for production (emits structured JSON with `trip_id`, `driver_id`, `rider_id`, `correlation_id` as top-level keys) and `DevFormatter` for development (human-readable). The `log_context()` context manager injects arbitrary key-value pairs onto every log record emitted from the current thread within the scope. `PIIFilter` redacts emails to `[EMAIL]` and phone numbers to `[PHONE]` before records reach any handler.

### Configuration

- Logger: Python `logging` (stdlib)
- Setup entry point: `setup_logging(level, json_output, environment)` in `services/simulation/src/sim_logging/setup.py`
- Levels used: DEBUG, INFO, WARNING, ERROR
- Format: JSON in production (`SIM_LOG_FORMAT=json`), human-readable text locally
- Noisy third-party loggers (`confluent_kafka`, `urllib3`) are silenced to WARNING at setup time

### Key Components

- `LogContext` — thread-local key-value store; values injected by `ContextFilter` into every log record on that thread
- `log_context()` / `log_trip_context()` — context managers that populate `LogContext` for a scope; clears all fields unconditionally on exit (nesting is not safe)
- `PIIFilter` — applied at handler level; masks emails and phone numbers via regex on plain-string messages only; only operates on plain `str` messages, not formatted arguments or structured fields
- `DefaultCorrelationFilter` — fallback that sets `correlation_id="-"` when none is present
- `CorrelationFilter` (from `src.core.correlation`) — attaches `correlation_id` and `session_id` from `contextvars` for distributed tracing
- `RequestLoggerMiddleware` — HTTP access logging middleware that resolves user identity from the `X-API-Key` header (session lookup for `sess_` keys, static for admin key, `anonymous` fallback) and emits structured access logs under logger `api.access`. Promotes HTTP audit fields (`method`, `path`, `status_code`, `duration_ms`, `user_identity`, `user_role`) to top-level JSON keys via `JSONFormatter`. Health check paths (`/health`, `/health/detailed`) are skipped to avoid probe log noise. Identity resolution happens after `call_next` returns (post-response).

### Locations

- `services/simulation/src/sim_logging/` — all logging infrastructure
- `services/simulation/src/api/middleware/` — `SecurityHeadersMiddleware` and `RequestLoggerMiddleware`
- `services/simulation/src/core/correlation.py` — `ContextVar`-based distributed tracing context
- All simulation modules — acquire loggers via `logging.getLogger(__name__)`

---

## Configuration

### Pattern

Pydantic Settings (`pydantic-settings`) with grouped environment variable prefixes. Each concern has its own `BaseSettings` subclass. Settings classes use `model_validator(mode="after")` to fail fast at startup if required credentials are absent — the service refuses to start silently without secrets. A singleton `get_settings()` accessor caches the composed settings tree for the simulation service.

### Sources

- Environment variables (primary), sourced at startup from a Docker volume populated by the `secrets-init` container reading LocalStack/AWS Secrets Manager
- Pydantic field defaults (fallback for non-credential settings)
- No static `.env` files for credentials — all secrets come from Secrets Manager

### Settings Classes (simulation)

| Class | Env Prefix | Purpose |
|-------|-----------|---------|
| `SimulationSettings` | `SIM_` | Engine behavior, speed, checkpoints, GPS thresholds |
| `KafkaSettings` | `KAFKA_` | Bootstrap servers, SASL credentials, schema registry |
| `RedisSettings` | `REDIS_` | Host, port, password |
| `OSRMSettings` | `OSRM_` | Routing service URL |
| `APISettings` | `API_` | API key |
| `MatchingSettings` | `MATCHING_` | Ranking weights, offer timeouts, retry intervals |
| `CORSSettings` | `CORS_` | Allowed origins |
| `PerformanceSettings` | `PERF_` | Metrics sampling rates |

### Locations

- `services/simulation/src/settings.py` — simulation settings tree
- `services/stream-processor/src/` — independent Pydantic Settings with `KAFKA_` and `REDIS_` prefixes
- `services/performance-controller/src/` — independent settings (no singleton; constructs fresh on each call)
- `services/bronze-ingestion/src/` — configuration via environment variables, lazy consumer construction

---

## Authentication and Authorization

### Authentication

Two distinct authentication mechanisms for the two protocols the simulation API serves:

- **REST (HTTP)**: API key passed via `X-API-Key` request header. Validated by a FastAPI dependency `Depends(verify_api_key)` injected on all protected routes.
- **WebSocket**: Browsers cannot send custom headers during the WebSocket upgrade. The API key is conveyed via the `Sec-WebSocket-Protocol: apikey.<key>` subprotocol header. The server echoes the subprotocol back on accept to satisfy the browser handshake.

The `/health` endpoint is intentionally unauthenticated for infrastructure probes (Kubernetes, load balancers).

**Dual key types**: `verify_api_key` accepts two key formats. Keys prefixed `sess_` are looked up in Redis via `session_store.get_session` and carry `role`/`email` from the stored `SessionData`. All other keys are compared against the static admin key from settings and receive `role="admin"`. This enables provisioned visitor accounts (role `"viewer"`) to authenticate alongside the static admin key without altering existing integrations.

**AuthContext**: An immutable frozen dataclass (`role`, `email`) returned by `verify_api_key`. Downstream route dependencies receive this instead of a raw string key. The `require_admin` dependency chains off `verify_api_key` and raises HTTP 403 when `role != "admin"`.

**Credential-based login**: `POST /auth/login` validates email/password against `user_store`, creates a Redis session via `session_store.create_session`, and returns a short-lived `api_key` alongside `role` and `email`. The frontend `LoginDialog` posts `{ email, password }`, receives `{ api_key, role, email }`, and persists the full session via `storeSession()`. Session keys carry a `sess_` prefix and are stored in Redis at `session:<key>` with TTL-based auto-eviction (default 24h).

For the production Lambda auth-deploy function, the API key is passed in the POST request body as an `api_key` field. Certain actions (`session-status`, `service-health`, `auto-teardown`, `get-deploy-progress`, `provision-visitor`, `extend-session`, `shrink-session`) are listed in `NO_AUTH_ACTIONS` and bypass key validation to enable frontend polling, EventBridge auto-teardown, and visitor self-registration without credentials.

### Authorization

Two roles exist — `admin` and `viewer`. All mutation endpoints (start/pause/resume/stop/reset simulation, set speed, create agents, toggle driver status, all puppet state transitions, set controller mode, register users) require the `require_admin` FastAPI dependency. Read-only endpoints accept any valid API key including viewer keys. Admin accounts are never created through the `POST /auth/register` endpoint — that endpoint is hardcoded to the `viewer` role and is called by the Lambda `provision-visitor` orchestrator.

In the frontend, `useRole()` reads the authenticated role from `sessionStorage` via `getSessionRole()`. All simulation controls and puppet agent actions are disabled for non-admin users and show `'Admin only'` tooltips.

### User Store and Session Store

`user_store.py` holds an in-memory registry keyed by email with bcrypt-hashed passwords (prefix `$2b$`). It is write-only at startup (provisioning); concurrent async reads are safe. Plaintext passwords are never retained after hashing.

`session_store.py` persists session keys as Redis hashes at `session:{api_key}` with a TTL. `delete_session` provides explicit invalidation for logout. `get_session` skips the Redis round-trip entirely for keys without the `sess_` prefix.

### Rate Limiting

`slowapi` middleware applies per-API-key rate limiting (fallback to IP). A separate `WebSocketRateLimiter` enforces a sliding-window limit of 5 WebSocket connections per 60 seconds per API key. `POST /auth/login` is rate-limited to 10/minute (stricter than other endpoints) to mitigate brute-force attacks. `POST /auth/register` is limited to 20/minute since it is called programmatically by the provisioning Lambda.

### Locations

- `services/simulation/src/api/auth.py` — `verify_api_key` FastAPI dependency, `AuthContext` dataclass, `require_admin`
- `services/simulation/src/api/websocket.py` — WebSocket subprotocol auth
- `services/simulation/src/api/rate_limit.py` — rate limiting middleware and WebSocket limiter
- `services/simulation/src/api/user_store.py` — bcrypt-hashed in-memory credential store
- `services/simulation/src/api/session_store.py` — Redis-backed session key persistence
- `services/simulation/src/api/routes/auth.py` — `POST /auth/login`, `GET /auth/validate`, `POST /auth/register`
- `services/control-panel/src/components/LoginDialog.tsx` — credential-based frontend login
- `services/control-panel/src/hooks/useRole.ts` — role resolution from `sessionStorage`
- `services/control-panel/src/utils/auth.ts` — `storeSession`, `clearSession`, `getApiKey`, `getSessionRole`
- `infrastructure/lambda/auth-deploy/` — Lambda-level API key validation and `NO_AUTH_ACTIONS`

---

## Data Access

### Pattern

Repository pattern with a `Generic[ModelT, DNAT]` base class (`BaseAgentRepository`) shared by `DriverRepository` and `RiderRepository`. Each repository encapsulates all CRUD for its entity and shields the engine from ORM details. `TripRepository` performs ORM-to-domain model translation (returning `TripDomain` objects); agent repositories return raw ORM objects.

Batch checkpoint writes use a delete-all-then-insert-all upsert strategy wrapped in a `savepoint` context for atomic rollback on failure — existing data is preserved if any insert fails.

Route caching is handled by `RouteCacheService` wrapping `OSRMClient` with an LRU cache (10,000 entries) keyed by H3 resolution-9 cell pairs. TTL expiry is enforced on read, not by a database constraint. Expired entries remain in the database until explicitly cleared.

### ORM / Database

- SQLAlchemy 2.0 ORM with SQLite as the checkpoint database (`SIM_DB_PATH`)
- S3-backed checkpoint storage available as an alternative (`SIM_CHECKPOINT_STORAGE_TYPE=s3`)
- Delta Lake tables (Bronze/Silver/Gold) accessed via `deltalake` (Rust-backed), PyArrow, and Trino SQL — not via SQLAlchemy

### Locations

- `services/simulation/src/db/repositories/` — `BaseAgentRepository`, `DriverRepository`, `RiderRepository`, `TripRepository`, `RouteCacheRepository`
- `services/simulation/src/db/schema.py` — SQLAlchemy ORM model definitions
- `services/simulation/src/db/transaction.py` — savepoint context manager
- `services/simulation/src/db/checkpoint.py` — SQLite checkpoint write/restore
- `services/simulation/src/db/s3_checkpoint.py` — S3 checkpoint backend
- `services/bronze-ingestion/src/writer.py` — Delta Lake write via `deltalake`
- `services/bronze-ingestion/src/dlq_writer.py` — DLQ Delta table write

---

## State Machines

### Pattern

Enum-based states with `VALID_TRANSITIONS` dictionaries that map each state to the set of states it may legally transition to. Terminal states map to empty sets, causing any further transition attempt to raise a `StateError`. State changes emit a Kafka event on every transition. The pattern is used for the trip lifecycle, simulation engine lifecycle, and driver status.

### Trip State Machine

10-state trip lifecycle: `REQUESTED -> OFFER_SENT <-> OFFER_EXPIRED / OFFER_REJECTED -> DRIVER_ASSIGNED -> EN_ROUTE_PICKUP -> AT_PICKUP -> IN_TRANSIT -> COMPLETED / CANCELLED`. `offer_sequence` increments on each `OFFER_SENT` transition to track how many drivers were tried. `COMPLETED` and `CANCELLED` are terminal — their `VALID_TRANSITIONS` entries are empty sets.

### Simulation Engine State Machine

4-state lifecycle: `STOPPED -> RUNNING -> DRAINING -> PAUSED -> RUNNING`. Pause is two-phase: `DRAINING` waits for in-flight trips and repositioning drivers to finish (up to 7200 simulated seconds) before transitioning to `PAUSED`. If quiescence is not reached, trips are force-cancelled.

### Locations

- `services/simulation/src/trip.py` — `TripState` enum and `VALID_TRANSITIONS` dict
- `services/simulation/src/engine/__init__.py` — `SimulationState` enum and lifecycle state machine
- `services/simulation/src/agents/driver_agent.py` — driver status transitions
- `services/simulation/src/matching/matching_server.py` — trip state transitions during the offer cycle

---

## Event-Driven Architecture

### Pattern

The simulation engine is the sole producer of all domain events. All events carry three distributed-tracing correlation fields via `CorrelationMixin`:

- `session_id` — identifies the simulation run
- `correlation_id` — the primary business entity (typically `trip_id`)
- `causation_id` — the `event_id` of the event that triggered this one

`EventFactory.create_for_trip()` reads `trip.last_event_id` as the `causation_id`, then overwrites `trip.last_event_id` with the new event's UUID (when `update_causation=True`), forming an ordered causal chain for the entire trip lifecycle.

Events flow through two independent consumer paths from Kafka:
1. **Real-time path**: Stream Processor -> Redis pub/sub -> Simulation API WebSocket -> Control Panel
2. **Batch path**: Bronze Ingestion -> Delta Lake -> Airflow/DBT -> Silver/Gold -> Trino -> Grafana

### Kafka Topics

8 application topics: `trips`, `gps_pings` (8 partitions, double others due to volume), `driver_status`, `surge_updates`, `ratings`, `payments`, `driver_profiles`, `rider_profiles`. All events are JSON Schema-validated via the Schema Registry before publication.

### Redis Pub/Sub

4 channels: `driver_updates`, `rider_updates`, `trip_updates`, `surge_updates`. State snapshots (`snapshot:drivers:<id>`, `snapshot:trips:<id>`, `snapshot:surge:<zone_id>`) with 30-minute TTL enable client reconnection without replaying full event history.

Deduplication: Stream Processor uses Redis `SET NX` with 1-hour TTL on `event_id` to idempotently skip Kafka at-least-once redeliveries.

### Locations

- `services/simulation/src/events/schemas.py` — `CorrelationMixin` and all event schema definitions
- `services/simulation/src/events/factory.py` — `EventFactory` with causation chaining
- `services/simulation/src/kafka/producer.py` — Kafka producer with schema validation and controlled corruption injection
- `services/stream-processor/src/` — Kafka-to-Redis bridge with windowed GPS aggregation
- `services/bronze-ingestion/src/` — Kafka-to-Delta ingestion with DLQ routing
- `services/simulation/src/redis_client/` — Redis pub/sub publisher and state snapshot manager

---

## Immutability

### Pattern

Agent DNA is frozen via Pydantic `model_config = ModelConfig(frozen=True)`. Profile fields in DNA cannot be mutated on the model; instead, `profile_mutations.py` generates new field values emitted as `*.updated` Kafka events for SCD Type 2 tracking in the warehouse.

Cross-thread state transfer uses frozen dataclasses. `AgentSnapshot`, `TripSnapshot`, and `SimulationSnapshot` are `frozen=True` dataclasses — the only safe mechanism for reading simulation state from the FastAPI thread without locks. The SimPy thread writes them atomically; the API thread reads without mutation risk.

Events are append-only with UUID identifiers. The Bronze layer stores `_raw_value` verbatim; no fields are extracted or mutated at ingestion.

### Locations

- `services/simulation/src/agents/dna.py` — `DriverDNA` and `RiderDNA` with `frozen=True`
- `services/simulation/src/engine/snapshots.py` — frozen dataclass snapshots for cross-thread reads
- `services/simulation/src/events/schemas.py` — append-only event schemas with UUID `event_id`
- `services/bronze-ingestion/src/writer.py` — verbatim `_raw_value` Bronze storage

---

## Geospatial Patterns

### H3 Spatial Indexing

H3 hexagonal grid at resolution 9 (~174 m edge length) is used for O(1) driver lookups. `DriverGeospatialIndex` indexes drivers by their current H3 cell. Matching queries use progressive k-ring expansion starting at k=5, doubling outward only if no candidates are found. The `ZoneAssignmentService` uses H3 resolution-9 cells as LRU cache keys for point-in-polygon zone assignment results.

### Distance and Routing

- Haversine distance for arrival detection and candidate filtering (with a flat-Earth bounding-box pre-filter for cheap rejection)
- OSRM provides real Sao Paulo road network routes (async `httpx` for FastAPI, sync `requests` for SimPy threads)
- `RouteCacheService` wraps OSRM with an LRU cache (10,000 entries) keyed by H3 cell pairs
- `GPSSimulator` adds Gaussian noise (10 m sigma, clamped at 15 m) and simulates signal dropout; interpolates positions along polylines using binary search on precomputed cumulative distances

### Traffic Modeling

`TrafficModel` scales OSRM base durations with sigmoid-smoothed multipliers: morning rush 7-9 AM (+40%), evening rush 5-7 PM (+40%), night 10:30 PM-5:30 AM (-15%). Effects are combined with `max` for overlapping periods.

### Coordinate Convention

GeoJSON standard `[lon, lat]` is used for zone geometry storage and Shapely operations. All other public-facing functions (distance, OSRM, H3) use `(lat, lon)` order. This inconsistency is documented with conversion comments in the codebase.

### Locations

- `services/simulation/src/matching/driver_geospatial_index.py` — H3-based spatial index with k-ring expansion
- `services/simulation/src/geo/zone_assignment.py` — H3-cached zone lookup
- `services/simulation/src/geo/osrm_client.py` — dual sync/async OSRM client
- `services/simulation/src/geo/route_cache.py` — LRU route cache
- `services/simulation/src/geo/gps_simulation.py` — GPS noise and polyline interpolation
- `services/simulation/src/geo/zones.py` — GeoJSON zone loading with STRtree spatial index

---

## SimPy Patterns

### Two-Thread Model

FastAPI/uvicorn runs on the main thread. The SimPy event loop runs on a daemon thread (`SimulationRunner`). Both share the same in-process object graph (engine, registries, producers) — there is no IPC boundary.

### ThreadCoordinator

All cross-thread state mutations flow through the `ThreadCoordinator` command queue. FastAPI sends typed `Command` objects via a `Queue`; the SimPy step loop calls `process_pending_commands()` each tick to drain and execute them, then signals the calling thread via `threading.Event`. Direct mutation of SimPy state from the FastAPI thread is not permitted.

`env.process()` is not thread-safe and must only be called from the SimPy thread. Code originating from the FastAPI/asyncio thread queues work into `_pending_trip_executions`, `_pending_deferred_offers`, or `_pending_offer_timeouts`; the SimPy thread drains these each tick.

### Generator-Based Agents

Each agent (`DriverAgent`, `RiderAgent`) runs as a generator-based SimPy process. Agents use `yield env.timeout(seconds)` to advance simulation time. Cross-thread coordination uses `asyncio.run_coroutine_threadsafe(coro, main_loop)` from SimPy thread to the asyncio event loop.

### Two-Phase Pause

`RUNNING -> DRAINING -> PAUSED`. During `DRAINING`, the SimPy loop keeps stepping so in-flight trips can complete. After quiescence (or force-cancel timeout), the state transitions to `PAUSED`.

### Spawn Queues

`AgentFactory` maintains four `deque`s (driver/rider x immediate/scheduled). Four SimPy spawner processes poll these queues at configurable rates, decoupling HTTP-level agent registration from SimPy process creation.

### Locations

- `services/simulation/src/engine/__init__.py` — `SimulationEngine`, state machine, `ThreadCoordinator` usage
- `services/simulation/src/engine/thread_coordinator.py` — command queue bridge
- `services/simulation/src/engine/agent_factory.py` — spawn queues
- `services/simulation/src/agents/driver_agent.py` — generator-based driver process
- `services/simulation/src/agents/rider_agent.py` — generator-based rider process

---

## Medallion Architecture

### Pattern

Three-layer Delta Lake lakehouse: Bronze (raw) -> Silver (clean, deduplicated) -> Gold (star schema). Orchestrated by Airflow with four DAGs. DBT handles Bronze-to-Silver and Silver-to-Gold transformations.

**Bronze**: Every record stores `_raw_value` (verbatim UTF-8 JSON) plus Kafka provenance fields (`_kafka_partition`, `_kafka_offset`, `_kafka_timestamp`, `_ingested_at`, `_ingestion_date`). Partitioned by `_ingestion_date`. Malformed messages route to `dlq_bronze_{topic}` tables.

**Silver**: DBT incremental models parse `_raw_value` JSON, deduplicate by `event_id`, and stage one row per event. `ShortCircuitOperator` skips if Bronze is empty.

**Gold**: Full-refresh DBT star schema. Dimensions use SCD Type 2 (`dim_drivers`, `dim_payment_methods`) via window functions (`lag`/`lead`) for `valid_from`, `valid_to`, `current_flag`. `fact_trips` joins to dimensions with temporal range joins.

### DBT Dual-Target Pattern

`profiles.yml` defines two targets:
- `duckdb` — reads Bronze via `delta_scan()` over S3/MinIO; results stored as a local DuckDB file. Used in local development and Airflow-orchestrated runs.
- `glue` — executes as AWS Glue Spark job with Hive Metastore catalog. Used in production.

Cross-database SQL differences are abstracted via `adapter.dispatch` macros in `macros/cross_db/`: `json_field`, `to_ts`, `epoch_seconds`, `split_string`, `safe_array_element`, `format_date`, `day_of_week`, `delta_source`. The `glue__*` and `default__*` variants delegate to `spark__*`.

The `generate_schema_name` macro is overridden so `+schema: silver` and `+schema: gold` map directly to database names without a prefix.

### Airflow DAGs

| DAG | Schedule | Purpose |
|-----|----------|---------|
| `dbt_silver_transformation` | Hourly | Bronze -> Silver incremental load |
| `dbt_gold_transformation` | Triggered by Silver | Silver -> Gold star schema rebuild |
| `delta_maintenance` | Daily 3 AM | OPTIMIZE then VACUUM on all Delta tables |
| `dlq_monitoring` | Every 15 min (offset) | DLQ error count alerting via DuckDB |

### Locations

- `services/bronze-ingestion/src/` — Kafka-to-Bronze ingestion pipeline
- `tools/dbt/models/staging/` — Silver staging models
- `tools/dbt/models/marts/` — Gold dimensions, facts, aggregates
- `tools/dbt/macros/cross_db/` — DuckDB/Spark dialect abstraction macros
- `services/airflow/dags/` — DAG definitions
- `tools/great-expectations/` — Silver and Gold data quality validation
- `schemas/lakehouse/schemas/` — PySpark StructType Bronze table definitions

---

## Observability

### Pattern

Two-layer observability stack per Python service:

1. **In-process rolling window** (`MetricsCollector`): Thread-safe singleton collecting time-stamped samples in bounded `deque` structures (60-second window). Produces `PerformanceSnapshot` on demand with rates, latency percentiles (avg/p95/p99), error counts, and queue depths. Queue/agent counts are registered as callbacks polled at snapshot time rather than pushed.

2. **OpenTelemetry OTLP export** (`prometheus_exporter.py`): OTel instruments (counters, histograms, observable gauges) push to OTel Collector via OTLP/gRPC. The collector routes metrics to Prometheus (remote_write), logs to Loki (filelog receiver reading Docker container logs), and traces to Tempo. Tempo generates derived metrics (service-graphs, span-metrics) and remote-writes them back to Prometheus.

Delta computation: OTel Counters are cumulative; the exporter tracks `_previous_*` state and adds only the delta each export cycle, converting absolute rolling-window counts to increments.

Observable gauges (e.g., `offers_pending`) are used where the value is resolved and cleared within the same SimPy tick — an UpDownCounter would report zero because the OTel export interval fires between ticks.

GPS pings are sampled at 1% for distributed tracing to limit OpenTelemetry overhead (~1,200 pings per trip). Non-GPS topics are always traced.

### Grafana Dashboard Categories

| Category | Datasources |
|----------|------------|
| Monitoring | Prometheus |
| Data Engineering | Trino + Prometheus |
| Business Intelligence | Trino |
| Operations | Prometheus + Trino |
| Performance | Prometheus / cAdvisor |

### Locations

- `services/simulation/src/metrics/collector.py` — `MetricsCollector` singleton
- `services/simulation/src/metrics/prometheus_exporter.py` — OTel instrument definitions and delta export
- `services/stream-processor/src/prometheus_exporter.py` — stream processor OTel export
- `services/performance-controller/src/metrics_exporter.py` — performance controller OTel export
- `services/otel-collector/` — OTel Collector pipeline configuration
- `services/prometheus/` — recording rules including `rideshare:infrastructure:headroom`
- `services/grafana/dashboards/` — five dashboard categories

---

## Testing

### Pattern

Unit tests use pytest with three custom markers applied via `@pytest.mark.*`:
- `@pytest.mark.unit` — fast, isolated, no external services
- `@pytest.mark.slow` — longer-running unit tests
- `@pytest.mark.critical` — must pass for deployment

Integration tests use `@pytest.mark.requires_profiles(...)` to declare which Docker Compose profiles are needed (`core`, `data-pipeline`, `monitoring`). The test session fixture starts only the required profiles.

### Key Fixtures

- `DNAFactory` — seeded Faker-backed factory for deterministic `DriverDNA` and `RiderDNA` objects with Brazil-locale data
- `dna_factory` — pytest fixture wrapping `DNAFactory(seed=42)`
- `mock_kafka_producer` — mock for the Kafka producer to avoid live broker in unit tests
- `mock_redis_client` — mock for Redis to avoid live server in unit tests
- `setup_zone_validator` — autouse fixture resetting the zone loader singleton to `fixtures/sample_zones.geojson` before each test

Credential environment variables (`KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `REDIS_PASSWORD`, `API_KEY`) are set via `os.environ.setdefault` at the top of `conftest.py` before any agent module is imported, because `Settings()` construction is fail-fast on missing credentials.

### API Contract Testing

`test_api_contract.py` validates the OpenAPI spec structurally and runs `npm run generate-types` against the frontend, asserting the committed `api.generated.ts` matches regenerated output. This enforces frontend/backend type sync across service boundaries.

### API Layer Test Isolation Patterns

The API test suite uses several isolation techniques specific to the simulation's module structure:

**Engine module mocking via `sys.modules`**: The `mock_engine_modules` fixture is `autouse=True` and patches `sys.modules["engine"]` directly before each test to prevent the heavyweight SimPy engine from importing. After each test it restores original module references and clears `api.*` entries so the next test reimports cleanly.

**Rate limiter state isolation**: Because `slowapi` stores counters on the `Limiter` instance (a module-level singleton), a second `autouse=True` fixture in `test_rate_limiting.py` purges all `api.*` module entries from `sys.modules` before and after each test to prevent rate limit counts bleeding across tests.

**Role-based access control testing**: `test_role_enforcement.py` uses `app.dependency_overrides[verify_api_key]` to inject a fixed `AuthContext` (role `viewer` or `admin`) without touching Redis. All `api.*` module entries are cleared from `sys.modules` before building each app to ensure a pristine import.

**Session key authentication**: Keys with a `sess_` prefix bypass the static key check and trigger a Redis hash lookup at `session:<key>`. The `mock_redis_client` fixture defaults `hgetall` to return `{}` so session lookups fail unless a test explicitly overrides the return value.

**UserStore singleton reset**: `test_user_store.py` resets the module-level singleton via `user_store_module._user_store = None` in an `autouse` fixture to prevent cross-test state pollution.

### Frontend Tests

Vitest with `@testing-library/react` for component testing. `jsdom` provides the DOM environment.

### DBT Tests

`schema.yml` generic tests (not-null, unique, relationships, accepted-values) plus custom generic tests in `tools/dbt/tests/generic/` and singular SQL tests in `tools/dbt/tests/singular/`.

### Locations

- `services/simulation/tests/conftest.py` — global fixture setup and credential injection
- `services/simulation/tests/factories.py` — `DNAFactory`
- `services/simulation/tests/api/` — FastAPI endpoint contract, role enforcement, session/user store, rate limiting tests
- `tests/integration/data_platform/` — full-stack integration tests against live Docker containers
- `tests/performance/` — container resource load tests with USL model fitting and Plotly report generation
- `tools/dbt/tests/` — DBT test definitions

---

## Dependency Injection and Wiring

### Pattern

Application components in the simulation service are constructed with `None` placeholders and patched after all objects exist (`deferred wiring`). For example, `matching_server._notification_dispatch`, `matching_server._registry_manager`, and `engine._agent_factory` are set in `main.py` after all objects are instantiated. This breaks circular construction dependencies but means components are not fully functional until `main()` completes all wiring steps.

FastAPI dependency injection (`Depends(...)`) is used for authentication (`verify_api_key`, `require_admin`) and for accessing `app.state.engine` from route handlers. `app.state.engine` and `app.state.simulation_engine` point at the same object — the duplicate key exists for backward compatibility after a rename.

Middleware is registered at app creation time. Two middleware classes are applied to every request: `SecurityHeadersMiddleware` (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) and `RequestLoggerMiddleware` (structured access logging with post-response identity resolution). WebSocket requests are not processed by `RequestLoggerMiddleware`.

### Locations

- `services/simulation/src/main.py` — application bootstrap and deferred wiring
- `services/simulation/src/api/app.py` — FastAPI application setup with lifespan and middleware
- `services/simulation/src/api/middleware/` — `SecurityHeadersMiddleware` and `RequestLoggerMiddleware`
- `services/simulation/src/api/routes/` — route handlers using `Depends(verify_api_key)` and `Depends(require_admin)`

---

## Secrets Management

### Pattern

All credentials are sourced from Secrets Manager (LocalStack in dev, AWS Secrets Manager in production). No credentials are hardcoded in `.env` files.

In local development: `localstack` starts first; `secrets-init` seeds LocalStack Secrets Manager and writes credential files to a shared Docker volume. All other services mount this volume read-only at `/secrets/` and source environment-specific `.env` files in their entrypoints. `seed-secrets.py` also generates bcrypt hashes at seed time for `rideshare/trino-admin-password-hash` and `rideshare/trino-visitor-password-hash` using the `bcrypt` library (requires `bcrypt` installed in the `secrets-init` container alongside `boto3`).

In production: External Secrets Operator bridges AWS Secrets Manager to Kubernetes Secrets. The `SecretStore` YAML is identical between dev and prod; only the ESO controller's endpoint env var differs (pointing at LocalStack vs. real AWS). All workload IAM roles use EKS Pod Identity (`pods.eks.amazonaws.com` trust) rather than IRSA.

**Visitor credential flow (two-phase)**: When a visitor registers via `provision-visitor` (Phase 1, pre-deploy), the Lambda:
1. Stores a PBKDF2 password hash in Secrets Manager at `rideshare/trino-visitor-password-hash-*` for Trino FILE authentication.
2. Encrypts the plaintext password with a KMS CMK (`rideshare-visitor-passwords`) and stores the ciphertext in DynamoDB (`rideshare-visitors` table, keyed on email hash).
3. Sends a SES welcome email.

Phase 2 (`reprovision-visitors`, post-deploy): scans DynamoDB, decrypts each KMS ciphertext, and creates ephemeral accounts in Grafana, Airflow, MinIO, and the Simulation API via co-located provisioning sub-modules. If SES delivery fails after DynamoDB write succeeds, the response is `{"provisioned": true, "email_sent": false}` with HTTP 500 — the visitor record is durable and Phase 2 will still succeed.

**Trino FILE-based passwords**: Trino uses a `password.db` file generated at pod/container startup by substituting `TRINO_ADMIN_PASSWORD_HASH` and `TRINO_VISITOR_PASSWORD_HASH` (bcrypt hashes, `$2b$10$` prefix) into `password.db.template` via `sed`/`envsubst`. The file is written with `chmod 600` to a shared `emptyDir` volume and never stored in a ConfigMap or Git. Password changes require a container restart — Trino reads `password.db` only at startup (`file.refresh-period=5s` applies to in-process polling after startup).

### Locations

- `infrastructure/scripts/` — `seed-secrets.py` (LocalStack seeding with bcrypt hash generation), `fetch-secrets.py` (credential retrieval), `generate_trino_password_hash.py`
- `infrastructure/scripts/provision_visitor_cli.py` — CLI orchestration of multi-service visitor provisioning
- `infrastructure/kubernetes/` — External Secrets Operator `SecretStore` and `ExternalSecret` manifests
- `infrastructure/terraform/foundation/modules/secrets_manager/` — Terraform module for AWS Secrets Manager resources
- `infrastructure/terraform/foundation/` — KMS CMK `rideshare-visitor-passwords`, DynamoDB `rideshare-visitors` table
- `infrastructure/lambda/auth-deploy/` — `get_secret()` helper normalizing plain-string and JSON-encoded secrets; two-phase visitor provisioning sub-modules
- `services/trino/etc/` — `password.db.template`, `rules.json`, `password-authenticator.properties`

---

## CI/CD Workflow Patterns

### Pattern

The GitHub Actions CI/CD pipeline uses several non-obvious patterns to manage infrastructure lifecycle and deployment correctness.

**`deploy` branch as materialized artifact**: The deploy workflow resolves runtime placeholders (`<account-id>`, `<acm-cert-arn>`, `<rds-endpoint>`, `<image-tag>`, `<alb-sg-id>`) directly into Kubernetes YAML files, then force-pushes the resolved files to the `deploy` branch with `[skip ci]`. ArgoCD watches the `deploy` branch with `selfHeal: true`. The `main` branch always retains placeholder tokens. Any unresolved placeholder in the `deploy` branch would cause ArgoCD to apply broken manifests.

**Phased convergence reporting**: The "Wait for EKS convergence" step waits for services in dependency order across five phases (infrastructure → schema → application → data-pipeline → UI). Each service reports readiness via `report-deploy-progress` to the Lambda, which stores it in the SSM session JSON. A marker-file pattern (`wait_and_mark` / `report_phase`) avoids read-modify-write races when multiple services are waited in parallel. `all_ready` becomes true when all 15 services have `ready: true`.

**State reconciliation before apply**: The deploy workflow runs `terraform import` for every known EKS resource before planning. This handles orphaned state from previous partial applies without requiring manual intervention.

**OSRM data sourcing**: The `build-images` workflow sources the Sao Paulo OSM `.pbf` file from an S3 build-assets bucket first (fast cache hit), falling back to Git LFS on miss and uploading to S3 for future builds. A size check guards against accidentally bundling an LFS pointer file.

**Lambda dependency packaging**: The deploy workflow installs Lambda dependencies with `--platform manylinux2014_x86_64 --only-binary=:all:` to produce a Linux-compatible package on the macOS/ubuntu runner before bundling and deploying. The `update-function-code` call causes Terraform to detect source-hash drift on the next plan — accepted as a no-op if no source changes occurred.

**Simulation build context**: The simulation service's Docker build context does not include `schemas/` by default (it lives at repo root). The CI step temporarily copies `schemas/` into `services/simulation/schemas` before the build and removes it after.

**Soft reset vs. teardown**: `teardown-platform` destroys EKS, RDS, and ALB but preserves S3 data and ECR images. `soft-reset` keeps all infrastructure intact but wipes all runtime state: Kafka (PVC delete+recreate), S3 lakehouse buckets, RDS databases (drop+recreate), Redis (FLUSHALL), and monitoring emptyDir volumes. The soft-reset temporarily suspends ArgoCD auto-sync to prevent it from fighting scale-down operations.

### Locations

- `.github/workflows/` — CI gate, build-images, deploy, teardown-platform, soft-reset, deploy-lambda workflows
- `infrastructure/terraform/` — state reconciliation and backend configuration
- `infrastructure/kubernetes/` — ArgoCD application definition and manifest templates

---

## Grafana Dashboard Conventions

### Pattern

All Grafana dashboards follow strict conventions to ensure provisioning-time correctness and maintainability.

**Hardcoded datasource UIDs**: Datasource UIDs (`prometheus`, `trino`, `loki`, `tempo`, `airflow-postgres`) are hardcoded directly in dashboard JSON. Template variable references like `${DS_PROMETHEUS}` are intentionally avoided — any UID change breaks every dashboard that references it.

**Trino panel requirements**: All Trino panels must set `"rawQuery": true` and use `"rawSQL"` (capital SQL) for the query field. The format field uses numeric values: `"format": 0` for table output, `"format": 1` for time series. String values are rejected by the plugin.

**Dashboard IDs**: The `id` field is always `null` — Grafana assigns IDs at provisioning time. IDs must never be committed.

**Admin dashboard folder**: A dedicated `Admin` Grafana folder (path `/etc/dashboards/admin`) holds operator-only dashboards. The `visitor-activity.json` dashboard aggregates per-service access timestamps from Airflow login history (via the `airflow-postgres` PostgreSQL datasource) and cross-service audit events from Loki. The `airflow-postgres` datasource must be provisioned and connected to `postgres-airflow:5432` before Grafana starts — absent datasource causes Airflow panels to fail silently.

**Error metrics absence**: `simulation_errors_total`, `stream_processor_validation_errors_total`, and `simulation_corrupted_events_total` only appear in Prometheus after the first error. On a healthy system these metrics are absent entirely — panels relying on them show "No data" rather than 0. Alert rules use `noDataState: NoData` to avoid false alerts from absent-but-normal metrics.

### Locations

- `services/grafana/dashboards/` — six dashboard categories (monitoring, data-engineering, business-intelligence, performance, operations, admin)
- `services/grafana/provisioning/datasources/datasources.yml` — hardcoded UIDs and datasource configuration
- `services/grafana/provisioning/dashboards/` — folder-to-path provider mappings
- `services/grafana/dashboards/admin/visitor-activity.json` — operator visitor activity audit dashboard
