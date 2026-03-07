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
- `PIIFilter` — applied at handler level; masks emails and phone numbers via regex on plain-string messages only
- `DefaultCorrelationFilter` — fallback that sets `correlation_id="-"` when none is present
- `CorrelationFilter` (from `src.core.correlation`) — attaches `correlation_id` and `session_id` from `contextvars` for distributed tracing

### Locations

- `services/simulation/src/sim_logging/` — all logging infrastructure
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

For the production Lambda auth-deploy function, the API key is passed in the POST request body as an `api_key` field. Certain actions (`session-status`, `service-health`, `auto-teardown`, `get-deploy-progress`) are listed in `NO_AUTH_ACTIONS` and bypass key validation to enable frontend polling and EventBridge auto-teardown without credentials.

### Authorization

Single shared API key grants full access to all simulation operations. There is no RBAC or per-endpoint permission differentiation.

### Rate Limiting

`slowapi` middleware applies per-API-key rate limiting (fallback to IP). A separate `WebSocketRateLimiter` enforces a sliding-window limit of 5 WebSocket connections per 60 seconds per API key.

### Locations

- `services/simulation/src/api/auth.py` — `verify_api_key` FastAPI dependency
- `services/simulation/src/api/websocket.py` — WebSocket subprotocol auth
- `services/simulation/src/api/rate_limit.py` — rate limiting middleware and WebSocket limiter
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

### Frontend Tests

Vitest with `@testing-library/react` for component testing. `jsdom` provides the DOM environment.

### DBT Tests

`schema.yml` generic tests (not-null, unique, relationships, accepted-values) plus custom generic tests in `tools/dbt/tests/generic/` and singular SQL tests in `tools/dbt/tests/singular/`.

### Locations

- `services/simulation/tests/conftest.py` — global fixture setup and credential injection
- `services/simulation/tests/factories.py` — `DNAFactory`
- `tests/integration/data_platform/` — full-stack integration tests against live Docker containers
- `tests/performance/` — container resource load tests with USL model fitting and Plotly report generation
- `tools/dbt/tests/` — DBT test definitions

---

## Dependency Injection and Wiring

### Pattern

Application components in the simulation service are constructed with `None` placeholders and patched after all objects exist (`deferred wiring`). For example, `matching_server._notification_dispatch`, `matching_server._registry_manager`, and `engine._agent_factory` are set in `main.py` after all objects are instantiated. This breaks circular construction dependencies but means components are not fully functional until `main()` completes all wiring steps.

FastAPI dependency injection (`Depends(...)`) is used for authentication (`verify_api_key`) and for accessing `app.state.engine` from route handlers.

### Locations

- `services/simulation/src/main.py` — application bootstrap and deferred wiring
- `services/simulation/src/api/app.py` — FastAPI application setup with lifespan and middleware
- `services/simulation/src/api/routes/` — route handlers using `Depends(verify_api_key)`

---

## Secrets Management

### Pattern

All credentials are sourced from Secrets Manager (LocalStack in dev, AWS Secrets Manager in production). No credentials are hardcoded in `.env` files.

In local development: `localstack` starts first; `secrets-init` seeds LocalStack Secrets Manager and writes credential files to a shared Docker volume. All other services mount this volume read-only at `/secrets/` and source environment-specific `.env` files in their entrypoints.

In production: External Secrets Operator bridges AWS Secrets Manager to Kubernetes Secrets. The `SecretStore` YAML is identical between dev and prod; only the ESO controller's endpoint env var differs (pointing at LocalStack vs. real AWS). All workload IAM roles use EKS Pod Identity (`pods.eks.amazonaws.com` trust) rather than IRSA.

### Locations

- `infrastructure/scripts/` — `seed-secrets.py` (LocalStack seeding), `fetch-secrets.py` (credential retrieval)
- `infrastructure/kubernetes/` — External Secrets Operator `SecretStore` and `ExternalSecret` manifests
- `infrastructure/terraform/foundation/modules/secrets_manager/` — Terraform module for AWS Secrets Manager resources
- `infrastructure/lambda/auth-deploy/` — `get_secret()` helper normalizing plain-string and JSON-encoded secrets
