# PATTERNS.md

> Observed code patterns in this codebase.

## Error Handling

How errors are handled across the codebase.

### Pattern

**Exception Hierarchy**: Custom exception classes inherit from base types to indicate retry semantics. `NetworkError` signals transient failures (Kafka delivery, OSRM timeout) that support retry with exponential backoff. `PermanentError` signals failures requiring immediate cancellation (no route found, invalid state transition).

**State Machine Validation**: State transitions are validated through `VALID_TRANSITIONS` dictionaries that define legal state changes. Invalid transitions raise `ValueError` with descriptive messages. Terminal states (COMPLETED, CANCELLED) reject all further transitions.

**Try-Except with Logging**: Exception blocks log the error with structured context (trip_id, driver_id, correlation_id) before raising or handling. Critical path errors (Kafka producer, database writes) are logged at ERROR level with exception stack traces.

**Graceful Degradation**: Non-critical failures are logged but don't halt execution. GPS ping emission errors log warnings but don't stop agent processes. Dead letter queues capture malformed messages for offline investigation.

### Locations

- `services/simulation/src/core/exceptions.py` — Custom exception hierarchy (NetworkError, PermanentError, TransientError)
- `services/simulation/src/trip.py` — Trip state machine with VALID_TRANSITIONS enforcement
- `services/simulation/src/engine/__init__.py` — Engine state machine validation
- `services/simulation/src/kafka/producer.py` — Kafka delivery error tracking with retry logic
- `services/bronze-ingestion/src/writer.py` — Dead letter queue routing for malformed messages

### Example

```python
# State machine validation
VALID_TRANSITIONS: dict[TripState, set[TripState]] = {
    TripState.REQUESTED: {TripState.OFFER_SENT, TripState.CANCELLED},
    TripState.STARTED: {TripState.COMPLETED},  # Cannot cancel once started
    # ...
}

def transition_to(self, new_state: TripState) -> None:
    if new_state not in VALID_TRANSITIONS[self.state]:
        raise ValueError(f"Invalid transition from {self.state} to {new_state}")
    self.state = new_state
```

## Logging

How logging is implemented across services.

### Pattern

**Structured Logging with Context**: Thread-local context storage automatically attaches correlation fields (trip_id, driver_id, rider_id, correlation_id) to all log records within a thread. Context is set via `log_context()` context manager.

**Dual Formatters**: JSON output for production (`JSONFormatter` with ISO timestamps, service metadata), human-readable format for development (`DevFormatter` with colored levels).

**PII Masking**: Global filter redacts emails and phone numbers from log messages using regex patterns, applied at handler level to prevent sensitive data leakage.

**Level Configuration**: Service-level log level set via `SIM_LOG_LEVEL`, `KAFKA_LOG_LEVEL` environment variables. Third-party libraries (confluent_kafka, urllib3) are suppressed to WARNING to reduce noise.

### Configuration

- **Logger**: Python `logging` module with custom formatters
- **Levels Used**: DEBUG (detailed traces), INFO (state transitions), WARNING (non-critical errors), ERROR (failures requiring intervention)
- **Format Selection**: Controlled by `SIM_LOG_FORMAT` env var (text|json)
- **Context Fields**: trip_id, driver_id, rider_id, correlation_id, session_id

### Locations

- `services/simulation/src/sim_logging/formatters.py` — JSONFormatter and DevFormatter implementations
- `services/simulation/src/sim_logging/context.py` — Thread-local context storage with log_context() manager
- `services/simulation/src/sim_logging/pii_filter.py` — PII masking filter for emails and phones
- `services/stream-processor/src/config.py` — Stream processor logging setup
- `services/bronze-ingestion/src/main.py` — Bronze ingestion logging configuration

### Example

```python
from sim_logging import log_context

with log_context(trip_id=trip.trip_id, driver_id=driver.driver_id):
    logger.info("Trip started")  # Automatically includes trip_id, driver_id
```

## Configuration

How configuration is managed across services.

### Pattern

**Pydantic Settings**: All services use `pydantic-settings` `BaseSettings` for environment-based configuration with validation. Settings classes define field types, defaults, constraints, and environment variable prefixes.

**Grouped Settings**: Related settings are grouped into separate classes (SimulationSettings, KafkaSettings, RedisSettings) with distinct `env_prefix` values (SIM_, KAFKA_, REDIS_).

**Singleton Pattern**: Settings accessed via `get_settings()` function using `@lru_cache(maxsize=1)` to ensure single instance per process.

**Validation at Startup**: Pydantic validators enforce required credentials, URL formats, and numeric ranges. Missing credentials raise `ValueError` with clear error messages during settings instantiation.

**Secret Injection**: Credentials are never hardcoded. All secrets are injected from LocalStack Secrets Manager via the `secrets-init` service, which writes profile-specific env files to `/secrets/` volume.

### Sources

- Environment variables (primary)
- `.env` files (development only, never committed)
- LocalStack Secrets Manager (via secrets-init service)
- Default values in Settings classes (non-sensitive only)

### Locations

- `services/simulation/src/settings.py` — Simulation, Kafka, Redis, OSRM, API settings
- `services/stream-processor/src/config.py` — Stream processor configuration
- `services/bronze-ingestion/src/config.py` — Bronze ingestion settings
- `infrastructure/scripts/seed-secrets.py` — Secrets initialization for LocalStack
- `infrastructure/docker/compose.yml` — secrets-init service orchestration

### Example

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class KafkaSettings(BaseSettings):
    bootstrap_servers: str = "localhost:9092"
    sasl_username: str = ""
    sasl_password: str = ""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    @model_validator(mode="after")
    def validate_credentials(self) -> "KafkaSettings":
        if not self.sasl_username or not self.sasl_password:
            raise ValueError("Kafka credentials required")
        return self
```

## Authentication & Authorization

How authentication is handled (authorization is not implemented).

### Authentication

**API Key Authentication**: Shared secret authentication via `X-API-Key` header for REST endpoints and `Sec-WebSocket-Protocol: apikey.<key>` for WebSocket connections.

**Dependency Injection**: FastAPI `Depends(verify_api_key)` dependency applied to protected routes. Authentication logic centralized in `api.auth.verify_api_key()`.

**Environment-Based Key**: API key loaded from `API_KEY` environment variable (injected by secrets-init). Missing or invalid keys return 401 Unauthorized.

**No User Model**: System uses single shared API key for all clients. No user accounts, sessions, or JWTs.

### Protected Endpoints

- `/simulation/*` — Simulation control (start, pause, stop)
- `/agents/*` — Agent placement and inspection
- `/puppet/*` — Puppet mode controls
- `/metrics/*` — Metrics snapshots

### Unprotected Endpoints

- `/health` — Health checks (for orchestration)
- `/health/detailed` — Detailed service status
- `/ws` — WebSocket (key verified via Sec-WebSocket-Protocol header)

### Locations

- `services/simulation/src/api/auth.py` — API key verification function
- `services/simulation/src/api/routes/*.py` — Protected routes with Depends(verify_api_key)
- `services/simulation/src/api/websocket.py` — WebSocket authentication via subprotocol

### Example

```python
from fastapi import Depends
from api.auth import verify_api_key

@router.post("/simulation/start", dependencies=[Depends(verify_api_key)])
async def start_simulation() -> dict:
    # Only accessible with valid X-API-Key header
    pass
```

## Data Access

How data is accessed and managed.

### Pattern

**Repository Pattern**: Data access abstracted through repository classes with CRUD operations. Repositories translate between SQLAlchemy ORM models and rich domain models.

**Generic Base Repository**: `BaseAgentRepository[ModelT, DNAT]` uses Python generics to share logic between `DriverRepository` and `RiderRepository`. Protocol constraints (`HasHomeLocation`) ensure type safety.

**Domain Model Translation**: Repositories expose domain models (tuple coordinates, enum states) while persisting as simple types (comma-separated strings, varchar). `_to_domain()` and `_from_domain()` methods handle bidirectional conversion.

**Batch Operations**: Checkpoint restore uses `batch_upsert_with_state()` for atomic agent state replacement. Uses savepoints for SQLite compatibility.

**Cache Repository**: H3-keyed route cache with TTL-based expiration (30 days default). Uses SQLite upsert (`INSERT ... ON CONFLICT DO UPDATE`) to avoid duplicate key errors.

### ORM/Database

- **Simulation State**: SQLite with SQLAlchemy ORM (checkpoint persistence)
- **Lakehouse Storage**: Delta Lake (MinIO/S3) via delta-rs Python bindings
- **Metadata Catalog**: Hive Metastore backed by PostgreSQL
- **Airflow Backend**: PostgreSQL
- **Caching**: Redis (state snapshots, pub/sub)

### Locations

- `services/simulation/src/db/repositories/base_agent_repository.py` — Generic repository base class
- `services/simulation/src/db/repositories/trip_repository.py` — Trip CRUD with domain translation
- `services/simulation/src/db/repositories/route_cache_repository.py` — H3-indexed route cache
- `services/bronze-ingestion/src/writer.py` — Delta Lake writes via pyarrow
- `tools/dbt/models/` — SQL transformations for lakehouse layers

### Example

```python
class BaseAgentRepository(Generic[ModelT, DNAT]):
    def get_by_id(self, agent_id: str) -> ModelT | None:
        orm_model = self._session.query(self._model_class).filter_by(id=agent_id).first()
        if not orm_model:
            return None
        return self._to_domain(orm_model)

    def _to_domain(self, orm_model: Any) -> ModelT:
        # Convert DB model to domain model (tuple coordinates, enums)
        pass
```

## State Machines

How state transitions are managed across entities.

### Pattern

**Enum-Based States**: States defined as string enums (TripState, SimulationState) with descriptive values matching event types.

**Transition Validation**: `VALID_TRANSITIONS` dictionaries map each state to its set of valid next states. `transition_to()` methods enforce these rules.

**Terminal States**: COMPLETED and CANCELLED states have empty valid transition sets, preventing any further state changes.

**Metadata on Transitions**: State transitions can attach metadata (cancellation_by, cancellation_reason, offer_sequence) that's immutable once set.

**Event Emission**: Each state transition triggers an event published to Kafka with the new state and transition timestamp.

### State Machines in System

**Trip Lifecycle** (10 states):
- Happy path: REQUESTED -> OFFER_SENT -> MATCHED -> DRIVER_EN_ROUTE -> DRIVER_ARRIVED -> STARTED -> COMPLETED
- Cancellation: Most states -> CANCELLED (except STARTED)
- Retries: OFFER_EXPIRED/OFFER_REJECTED -> OFFER_SENT

**Simulation Engine** (4 states):
- STOPPED -> RUNNING -> DRAINING -> PAUSED -> RUNNING (cycle)

**Driver Status** (5 states):
- offline -> idle -> driving_to_pickup -> on_trip -> idle (cycle)

### Locations

- `services/simulation/src/trip.py` — Trip state machine with VALID_TRANSITIONS
- `services/simulation/src/engine/__init__.py` — Simulation state machine
- `services/simulation/src/agents/driver_agent.py` — Driver status state management
- `tools/dbt/models/staging/stg_trips.sql` — Trip state parsing in Silver layer

### Example

```python
class TripState(str, Enum):
    REQUESTED = "requested"
    STARTED = "started"
    COMPLETED = "completed"

VALID_TRANSITIONS = {
    TripState.REQUESTED: {TripState.OFFER_SENT, TripState.CANCELLED},
    TripState.STARTED: {TripState.COMPLETED},  # Cannot cancel
}

def transition_to(self, new_state: TripState) -> None:
    if new_state not in VALID_TRANSITIONS[self.state]:
        raise ValueError(f"Invalid transition")
    self.state = new_state
```

## Immutable Data Patterns

How immutability is enforced for critical data.

### Pattern

**Frozen Dataclasses**: Agent DNA models use Pydantic `ConfigDict(frozen=True)` to prevent modification after creation. Behavioral parameters (acceptance_rate, patience_threshold) remain constant throughout agent lifetime.

**Event Immutability**: All events are append-only facts with unique `event_id` (UUID). Events represent point-in-time observations and are never updated.

**Snapshot Models**: Engine state snapshots use frozen dataclasses for thread-safe transfer between FastAPI and SimPy threads.

**Profile vs DNA Separation**: DNA contains immutable behavioral parameters; profile contains mutable attributes (vehicle_model, phone number). Profile updates trigger new events but DNA never changes.

### Locations

- `services/simulation/src/agents/dna.py` — Frozen DriverDNA and RiderDNA models
- `services/simulation/src/events/schemas.py` — Immutable event schemas with UUID identifiers
- `services/simulation/src/engine/snapshots.py` — Frozen snapshot dataclasses
- `services/simulation/src/agents/statistics.py` — Session-only statistics (reset on restart)

### Example

```python
class DriverDNA(BaseModel):
    model_config = ConfigDict(frozen=True)  # Immutable

    # Behavioral parameters (never change)
    acceptance_rate: float
    service_quality: float

    # Profile attributes (can change via events)
    vehicle_make: str
    phone: str
```

## Event-Driven Architecture

How events flow through the system.

### Pattern

**Single Source of Truth**: Simulation publishes all events exclusively to Kafka. Stream processor consumes Kafka and publishes to Redis for frontend. No direct Redis publishing from simulation eliminates duplicate events.

**Distributed Tracing**: All events include correlation fields (session_id, correlation_id, causation_id) for tracking event chains across services.

**Schema-First Design**: Event schemas defined as Pydantic models in `events/schemas.py`. JSON schemas registered with Confluent Schema Registry for validation.

**At-Least-Once Delivery**: Manual Kafka offset commits after successful downstream processing (Redis publish, Delta write) ensures no data loss on consumer failure.

**Topic-Per-Event-Type**: Eight Kafka topics segregate event types (trips, gps_pings, driver_status, surge_updates, ratings, payments, driver_profiles, rider_profiles).

**Event Deduplication**: Stream processor uses Redis SET NX with TTL to track processed event_id values, preventing duplicate processing.

### Event Flow

```
Simulation -> Kafka Topics -> Stream Processor -> Redis Pub/Sub -> WebSocket -> Frontend
                           |
                           v
                      Bronze Ingestion -> Delta Lake -> DBT (Silver/Gold) -> Trino -> Grafana
```

### Locations

- `services/simulation/src/events/schemas.py` — Canonical event schema definitions
- `services/simulation/src/kafka/producer.py` — Kafka producer with idempotent publishing
- `services/stream-processor/src/handlers/` — Per-topic event handlers
- `services/bronze-ingestion/src/consumer.py` — Kafka-to-Delta ingestion
- `schemas/kafka/` — JSON schema definitions for Schema Registry

### Example

```python
class CorrelationMixin(BaseModel):
    session_id: str  # Simulation run ID
    correlation_id: str  # Request trace ID
    causation_id: str | None  # Event that caused this event

class TripEvent(CorrelationMixin):
    event_id: str  # Unique event identifier (UUID)
    event_type: Literal["trip.requested", "trip.started", ...]
    trip_id: str
    timestamp: datetime
```

## Geospatial Patterns

How geographic data is handled.

### Pattern

**H3 Spatial Indexing**: Driver locations indexed using Uber H3 hexagons at resolution 7 (~5km edge length) for O(1) neighbor lookups during matching. H3 cells enable efficient proximity searches without distance calculations.

**Zone Validation**: All coordinates validated against Sao Paulo district boundaries using point-in-polygon checks. Invalid locations rejected during DNA creation.

**Haversine Distance**: Distance calculations use haversine formula for great-circle distance on Earth's surface. Used for arrival detection (within 50m threshold) and destination validation (within 20km of home).

**Route Progress Tracking**: Routes stored as coordinate arrays with progress indices. Frontend visualizes driver position by incrementing index rather than re-transmitting full geometry.

**OSRM Integration**: External OSRM routing service provides route geometry and duration. Retry logic with exponential backoff handles transient failures.

### Locations

- `services/simulation/src/matching/h3_index.py` — H3-based spatial index for drivers
- `services/simulation/src/agents/zone_validator.py` — Point-in-polygon zone validation
- `services/simulation/src/agents/dna.py` — Haversine distance calculations
- `services/simulation/src/geo/osrm_client.py` — OSRM client with retry logic
- `services/simulation/data/zones.geojson` — Sao Paulo district boundaries

### Example

```python
# H3 spatial indexing for O(1) lookups
driver_index: dict[str, set[str]] = {}  # h3_cell -> driver_ids

def add_driver(driver_id: str, lat: float, lon: float) -> None:
    h3_cell = h3.latlng_to_cell(lat, lon, resolution=7)
    driver_index.setdefault(h3_cell, set()).add(driver_id)

def nearby_drivers(lat: float, lon: float) -> set[str]:
    h3_cell = h3.latlng_to_cell(lat, lon, resolution=7)
    neighbors = h3.grid_ring(h3_cell, k=1)  # 1-ring of neighbors
    return {d for cell in neighbors for d in driver_index.get(cell, set())}
```

## Discrete-Event Simulation

How SimPy simulation patterns are implemented.

### Pattern

**Generator-Based Processes**: Agent behaviors modeled as Python generators that `yield` SimPy events (timeouts, resources). SimPy environment schedules and advances these coroutines.

**Two-Phase Pause**: RUNNING -> DRAINING -> PAUSED protocol ensures no trips are mid-execution during checkpointing. Drain process monitors active trips with 7200-second timeout.

**ThreadCoordinator**: Command queue pattern bridges FastAPI main thread and SimPy background thread. Commands (start, pause, place_agent) are queued and processed during SimPy step() cycle.

**Time Management**: TimeManager converts between SimPy unitless time (seconds elapsed) and datetime objects using simulation start time and speed multiplier.

**Agent Factory Reference**: Engine holds AgentFactory reference to enable continuous spawning processes that dynamically create agents at configured rates.

### Locations

- `services/simulation/src/engine/__init__.py` — SimulationEngine with two-phase pause
- `services/simulation/src/engine/thread_coordinator.py` — Thread-safe command queue
- `services/simulation/src/engine/time_manager.py` — Time conversion utilities
- `services/simulation/src/agents/driver_agent.py` — Generator-based agent processes
- `services/simulation/src/trips/trip_executor.py` — Trip execution as SimPy process

### Example

```python
# Generator-based agent process
def run(self) -> Generator:
    while True:
        # Wait for shift to start
        yield self.env.timeout(shift_wait_time)

        # Go online
        self.status = "idle"

        # Wait for shift duration
        yield self.env.timeout(shift_duration)

        # Go offline
        self.status = "offline"
```

## Medallion Architecture

How data lakehouse layers are implemented.

### Pattern

**Bronze Layer**: Raw Kafka events stored as Delta tables with fixed metadata schema (_raw_value, _kafka_partition, _kafka_offset, _kafka_timestamp, _ingested_at, _ingestion_date). No parsing or validation.

**Silver Layer**: DBT staging models parse JSON from Bronze `_raw_value`, deduplicate, validate coordinates, standardize timestamps. Incremental materialization with `_ingested_at` watermark.

**Gold Layer**: Star schema dimensional model with SCD Type 2 for slowly changing dimensions (driver profiles). Facts, dimensions, and pre-computed aggregates.

**Empty Source Guard**: Custom DBT macro prevents Delta Lake errors when Bronze tables exist but have no data. Required for Spark compatibility.

**Dead Letter Queue**: Malformed messages routed to `dlq_bronze_*` tables with error metadata for offline investigation.

### Transformations

**Bronze -> Silver**:
- JSON parsing via `get_json_object()`
- Deduplication via `ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at DESC)`
- Coordinate validation (latitude -90 to 90, longitude -180 to 180)
- Timestamp standardization to UTC

**Silver -> Gold**:
- Surrogate key generation via `ROW_NUMBER() OVER (ORDER BY ...)`
- SCD Type 2 tracking with valid_from/valid_to
- Star schema joins (facts -> dimensions)
- Pre-aggregation for dashboard performance

### Locations

- `services/bronze-ingestion/src/writer.py` — Bronze Delta table writes
- `tools/dbt/models/staging/` — Silver layer transformations
- `tools/dbt/models/marts/dimensions/` — Gold dimension tables with SCD Type 2
- `tools/dbt/models/marts/facts/` — Gold fact tables
- `tools/dbt/macros/source_with_empty_guard.sql` — Empty source guard macro

### Example

```sql
-- Silver layer with empty source guard
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='event_id'
) }}

WITH source AS (
    {{ source_with_empty_guard('bronze_trips') }}
),
parsed AS (
    SELECT
        get_json_object(_raw_value, '$.trip_id') AS trip_id,
        get_json_object(_raw_value, '$.event_type') AS event_type,
        _ingested_at
    FROM source
)
SELECT * FROM parsed
{% if is_incremental() %}
WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
{% endif %}
```

## Observability Patterns

How metrics, logs, and traces are collected.

### Pattern

**OpenTelemetry Integration**: Automatic instrumentation for FastAPI, Redis, and HTTPX using OpenTelemetry libraries. Manual spans for critical operations (Kafka produce, trip execution).

**Dual Metrics Collection**: In-memory collector tracks rolling window metrics (60s) for API responses. OTel exporter pushes metrics to Collector via OTLP gRPC.

**Three Pillars via OTel Collector**: Metrics -> Prometheus (remote_write), Logs -> Loki (push API), Traces -> Tempo (OTLP gRPC). OTel Collector acts as unified telemetry gateway.

**Correlation Bridging**: correlation_id from distributed tracing context attached as span attribute, enabling cross-service trace propagation.

**Observable Gauges**: Metrics like average fare use OTel observable gauges with callback-based reads from thread-safe snapshot dictionary.

### Configuration

- **Metrics Backend**: Prometheus (7d retention, scrape + remote_write)
- **Log Backend**: Loki with label-based indexing
- **Trace Backend**: Tempo with span storage
- **Export Protocol**: OTLP gRPC to OTel Collector
- **Instrumentation**: Automatic (FastAPI, Redis, HTTPX) + Manual spans

### Locations

- `services/simulation/src/metrics/prometheus_exporter.py` — OTel metrics export
- `services/simulation/src/main.py` — OpenTelemetry SDK initialization
- `services/otel-collector/otel-collector-config.yaml` — OTel Collector pipelines
- `services/grafana/provisioning/datasources/` — Grafana datasource configuration
- `services/prometheus/prometheus.yml` — Prometheus scrape and remote_write config

### Example

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Automatic instrumentation
FastAPIInstrumentor.instrument_app(app)

# Manual span
tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("kafka.produce") as span:
    span.set_attribute("messaging.destination.name", topic)
    producer.produce(topic, value)
```

---

**Generated**: 2026-02-13
**Codebase**: rideshare-simulation-platform
**Patterns Documented**: 12 major patterns
**Services Analyzed**: 8 Python services, 1 TypeScript service, DBT transformations
