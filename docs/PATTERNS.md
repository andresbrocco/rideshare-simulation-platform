# PATTERNS.md

> Code patterns and conventions observed in this codebase.

## Error Handling

### Hierarchical Exception Classification

**Pattern**: Two-tier exception hierarchy determines retry behavior declaratively.

**Location**: `services/simulation/src/core/exceptions.py`

**Implementation**:
```python
class SimulationError(Exception):
    """Base exception for all simulation errors."""
    pass

class TransientError(SimulationError):
    """Retryable errors (network timeouts, temporary unavailability)."""
    pass

class PermanentError(SimulationError):
    """Non-retryable errors (validation failures, business logic violations)."""
    pass
```

**Usage**: Retry logic in `services/simulation/src/core/retry.py` checks `isinstance(error, TransientError)` to decide whether to retry. This keeps retry decisions out of business logic.

### Graceful Degradation

**Pattern**: Non-critical failures are logged but don't crash the system.

**Location**: `services/simulation/src/kafka/producer.py`

**Implementation**: Kafka publishing uses reliability tiers:
- **Tier 1 (Critical)**: Trip state changes, payments - synchronous delivery confirmation with retries
- **Tier 2 (High-Volume)**: GPS pings, driver status - fire-and-forget with error logging

## Logging

### Structured JSON Logging

**Pattern**: Thread-local context propagation via LogRecordFactory replacement.

**Location**: `services/simulation/src/sim_logging/`

**Implementation**:
- `JSONFormatter` produces structured JSON logs for production
- `DevFormatter` produces human-readable logs for development
- `log_context()` context manager attaches correlation IDs to all logs in scope
- Thread-local storage ensures context isolation across concurrent requests

**Key Feature**: Correlation ID flows from API request through Kafka events to downstream services.

### PII Masking

**Pattern**: Regex-based filtering masks sensitive data before logging.

**Location**: `services/simulation/src/sim_logging/filters.py`

**Implementation**:
```python
class PIIFilter(logging.Filter):
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    PHONE_PATTERN = re.compile(r'\d{3}[-.]?\s?\d{3}[-.]?\s?\d{4}')
```

Emails become `[EMAIL]`, phone numbers become `[PHONE]`.

## Configuration

### Pydantic Settings

**Pattern**: Hierarchical configuration with environment variable prefixes.

**Location**: `services/simulation/src/settings.py`

**Implementation**:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIM_")

    speed_multiplier: int = Field(ge=1, le=1024, default=1)
    log_level: str = "INFO"
```

**Prefixes**:
- `SIM_*` - Simulation settings
- `KAFKA_*` - Kafka/Schema Registry
- `REDIS_*` - Redis connection
- `OSRM_*` - Routing service
- `API_*` - API authentication
- `CORS_*` - CORS configuration

## Authentication

### API Key Authentication

**Pattern**: Shared secret with different transport mechanisms for REST vs WebSocket.

**Location**: `services/simulation/src/api/auth.py`

**Implementation**:
- REST: `X-API-Key` header
- WebSocket: `Sec-WebSocket-Protocol: apikey.<key>` (works around browser limitations)

**Rationale**: Browser WebSocket API doesn't support custom headers, so API key is encoded in the subprotocol negotiation.

## Data Access

### Repository Pattern

**Pattern**: Domain-specific repositories abstract database operations.

**Location**: `services/simulation/src/db/`

**Repositories**:
- `DriverRepository` - Driver agent persistence
- `RiderRepository` - Rider agent persistence
- `TripRepository` - Trip state persistence
- `CheckpointManager` - Simulation checkpoint/recovery

**Implementation**: SQLAlchemy ORM with explicit session management. Repositories accept session as parameter for transaction control.

## Event-Driven Architecture

### Kafka-Centric Event Flow

**Pattern**: Single source of truth with separate stream processor.

**Flow**:
```
Simulation → Kafka → Stream Processor → Redis → WebSocket → Frontend
```

**Key Decision**: Simulation publishes exclusively to Kafka. A separate `stream-processor` service consumes from Kafka and publishes to Redis pub/sub. This eliminates duplicate events and ensures consistent ordering.

**Location**:
- Producer: `services/simulation/src/kafka/producer.py`
- Consumer: `services/stream-processor/src/processor.py`

### Reliability Tiers

**Pattern**: Different delivery guarantees based on event criticality.

| Tier | Events | Guarantee |
|------|--------|-----------|
| 1 (Critical) | Trip states, payments, ratings | Synchronous ack with retry |
| 2 (High-Volume) | GPS pings, driver status | Fire-and-forget |

## State Machine

### Trip State Machine

**Pattern**: Validated finite state machine with 10 states.

**Location**: `services/simulation/src/trip.py`

**States**:
```
REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED
                ↓
         OFFER_EXPIRED/REJECTED → (retry cycle)
                ↓
            CANCELLED (terminal)
```

**Implementation**: `TripState` enum with `VALID_TRANSITIONS` dict. State changes validated before mutation.

**Protection**: `STARTED` state cannot transition to `CANCELLED` (rider is in vehicle).

## Immutability

### Agent DNA vs Profile

**Pattern**: Immutable behavioral DNA, mutable profile attributes.

**Location**: `services/simulation/src/agents/dna.py`

**Implementation**:
- **DNA** (frozen dataclass): Acceptance rates, patience thresholds, service quality - never changes
- **Profile**: Vehicle info, contact details - can change with SCD Type 2 tracking

**Rationale**: DNA represents inherent behavioral characteristics. Profile represents changeable attributes like phone number or vehicle.

## Checkpoint & Recovery

### Two-Phase Pause

**Pattern**: Graceful pause drains in-flight operations before checkpointing.

**Location**: `services/simulation/src/engine/engine.py`

**Phases**:
1. **Pause Requested**: Stop accepting new trips, signal agents to complete current work
2. **Quiescent**: All in-flight trips completed, safe to checkpoint

**Implementation**: `ThreadCoordinator` tracks active operations. Checkpoint only occurs when count reaches zero.

### Checkpoint Types

**Pattern**: Different recovery strategies for graceful vs crash checkpoints.

**Location**: `services/simulation/src/db/checkpoint_manager.py`

| Type | Trigger | Recovery |
|------|---------|----------|
| Graceful | Explicit pause | Full state restoration |
| Crash | Periodic timer | Rollback incomplete trips |

## Geospatial

### H3 Spatial Indexing

**Pattern**: Hexagonal hierarchical spatial index for driver matching.

**Location**: `services/simulation/src/geo/spatial_index.py`

**Implementation**: H3 resolution 7 (~5.16 km² hexagons) for driver geospatial queries. Drivers indexed by H3 cell for O(1) neighbor lookups.

### Route Caching

**Pattern**: LRU cache keyed by H3 cell pairs.

**Location**: `services/simulation/src/geo/route_cache.py`

**Implementation**: Routes between H3 cells are cached to reduce OSRM calls. Cache key is `(origin_h3, destination_h3)` tuple.

### Dual-Strategy Zone Assignment

**Pattern**: Point-in-polygon with H3 fallback.

**Location**: `services/simulation/src/geo/zone_assignment.py`

**Strategy**:
1. Try exact point-in-polygon test against zone boundaries
2. If no match (boundary edge cases), use H3 cell to zone mapping

## Medallion Architecture

### Bronze → Silver → Gold

**Pattern**: Layered data transformation with increasing quality.

**Locations**:
- Bronze: `services/spark-streaming/` (Kafka → Delta)
- Silver: `services/dbt/models/staging/` (cleaning, deduplication)
- Gold: `services/dbt/models/marts/` (star schema, aggregates)

### Empty Source Guard

**Pattern**: Prevent Delta Lake errors when source tables are empty.

**Location**: `services/dbt/macros/empty_source_guard.sql`

**Implementation**: Macro checks if source has rows before transformation. Returns empty result set with correct schema if source is empty.

**Rationale**: Delta Lake throws `DeltaAnalysisException` on empty table operations. Guard macro prevents this.

### SCD Type 2

**Pattern**: Slowly Changing Dimension Type 2 for profile history.

**Location**: `services/dbt/models/marts/dim_drivers.sql`, `dim_riders.sql`

**Implementation**: Profile changes tracked with `valid_from`, `valid_to`, `is_current` columns. New record created on each profile update.

## Windowed Aggregation

### GPS Buffering

**Pattern**: Time-window batching reduces message volume.

**Location**: `services/stream-processor/src/handlers/gps_handler.py`

**Implementation**: GPS pings aggregated in 100ms windows. Only latest position per driver published to Redis. Reduces frontend message rate by ~10x.

**Strategies**:
- `latest`: Keep most recent ping per driver (default)
- `sample`: Random sampling within window

## Testing

### Factory Pattern for Test Data

**Pattern**: Seeded factories for deterministic test data.

**Location**: `services/simulation/tests/factories.py`

**Implementation**:
```python
class DNAFactory:
    def __init__(self, seed: int = 42):
        self.fake = Faker(['pt_BR'])
        Faker.seed(seed)
```

**Rationale**: Seeded Faker ensures reproducible test data across runs.

### Fixture Scope Strategy

**Pattern**: Session-scoped Docker, function-scoped table cleanup.

**Location**: `tests/integration/data_platform/conftest.py`

**Implementation**:
- Session scope: Docker containers, Kafka producer, Thrift connection
- Function scope: Table truncation between tests

**Rationale**: Container startup is slow (~60s). Keeping containers alive across tests with table cleanup is faster than restart.

## Naming Conventions

### Module Naming

| Suffix | Responsibility |
|--------|----------------|
| `*Repository` | Database access layer |
| `*Handler` | Event processors |
| `*Manager` | Lifecycle coordination |
| `*Controller` | API command translation |
| `*Service` | Stateful business logic |
| `*Client` | External service integration |

**Reference**: `docs/NAMING_CONVENTIONS.md`

---

**Generated**: 2026-01-21
**Codebase**: rideshare-simulation-platform
**Patterns Documented**: 15 major patterns
