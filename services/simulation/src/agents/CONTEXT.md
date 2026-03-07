# CONTEXT.md — Agents

## Purpose

Defines the behavioral models and SimPy process logic for the two participant types in the rideshare simulation: `DriverAgent` and `RiderAgent`. Each agent combines immutable DNA (behavioral parameters) with mutable profile attributes, runs as a generator-based SimPy process, and emits domain events to Kafka for downstream consumption.

## Responsibility Boundaries

- **Owns**: Agent DNA schema and generation, autonomous SimPy process loops, event emission to Kafka, session-only statistics tracking, profile mutation generation for SCD Type 2 events, zone and distance validation for agent locations
- **Delegates to**: `engine` (match requests via `asyncio.run_coroutine_threadsafe`), `matching` (offer handling and surge pricing), `geo` (zone lookup, OSRM routes, Haversine distance), `trips` (drive simulation along route), `kafka` (message production), `db.repositories` (persistence)
- **Does not handle**: Trip lifecycle management (owned by `engine`/`matching`), real-time Redis publishing (owned by `stream-processor`), fare computation beyond the `FareCalculator` call in `RiderAgent`

## Key Concepts

**DNA** (`dna.py`): A frozen Pydantic model split into two field categories. Behavioral parameters (e.g., `acceptance_rate`, `patience_threshold`) are immutable and govern decision-making throughout the agent's lifetime. Profile fields (e.g., `vehicle_make`, `email`) are logically mutable — they cannot be changed on the frozen model itself, but `profile_mutations.py` generates new values that are emitted as `*.updated` profile events for SCD Type 2 tracking in the data warehouse.

**Puppet mode**: Agents can be created with `puppet=True`, which causes them to skip all autonomous SimPy lifecycle behavior (offer acceptance, trip requests) and only emit GPS pings. This is used for externally-controlled agents driven through the API.

**Ephemeral agents**: A flag (`_is_ephemeral`) marks non-persisted puppet agents that exist in-memory only and are not written to the database.

**NextAction / ActionHistory**: Each agent tracks its next scheduled future action (`NextAction`) and a ring buffer of past actions (`deque(maxlen=200)`). These are used by the API inspection layer to show human-readable agent state.

**EventEmitter mixin** (`event_emitter.py`): Base class for both agents. Publishes events exclusively to Kafka. The `redis_channel` parameter is retained for backward compatibility but is ignored — Redis publishing is done by the stream-processor service consuming from Kafka.

**Profile update loop**: A background SimPy process runs alongside each non-puppet agent, firing every ~7 simulated days (configurable via `PROFILE_UPDATE_INTERVAL_SECONDS`) with random variance (0.5x–1.5x) to prevent synchronized updates. On each tick it calls `mutate_*_profile()` to pick one changed field and emits a `*.updated` event.

**Surge threshold retry loop**: Before a `RiderAgent` commits to a trip request, it polls the current surge multiplier for the pickup zone. If surge exceeds `dna.max_surge_multiplier`, the rider waits 30–120 seconds and retries. The rider only formally transitions to `requesting` status after passing the surge check.

## Non-Obvious Details

- DNA `home_location` and rider `frequent_destinations` are validated on construction using a point-in-polygon check against all 96 São Paulo district zones from `zones.geojson`. Invalid coordinates raise `ValueError` at model creation time.
- `RiderDNA.frequent_destinations` entries must be within 20 km of `home_location`, enforced via a Pydantic `field_validator` that runs Haversine distance checks. The destination distance validator depends on `home_location` being validated first, so field order in the model matters.
- Cross-thread coordination: `RiderAgent.run()` calls `asyncio.run_coroutine_threadsafe(match_coro, main_loop)` to submit match requests from the SimPy thread to the asyncio event loop running on the main thread.
- Ratings use a probabilistic submission model: exceptional ratings (1–2 stars or 5 stars) are submitted 85% of the time; mediocre ratings (3–4) only 60% of the time, creating a realistic submission bias.
- `DriverAgent.from_database()` and `RiderAgent.from_database()` bypass `__init__` (using `cls.__new__`) to avoid re-persisting agents that already exist in the database and to skip the creation event emission.
- GPS ping intervals differ by state: moving agents ping every `GPS_PING_INTERVAL_MOVING` seconds (default 2s), idle drivers ping every `GPS_PING_INTERVAL_IDLE` seconds (default 10s). Both are configurable via environment variables.
- The `EventEmitter._emit_to_kafka()` method may intentionally produce a second, corrupted copy of each event when the `SerializerRegistry` fires a corruption injection. This is a deliberate data quality testing feature, not a bug.
- `faker_provider.py` provides a custom Faker extension with Brazilian locale methods (`vehicle_br`, `license_plate_br`, `phone_br_mobile_sp`, `payment_method_br`) used by both `dna_generator.py` and `profile_mutations.py`.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
- [services/simulation/src/db/repositories](../db/repositories/CONTEXT.md) — Dependency — SQLAlchemy-backed persistence for simulation runtime state: drivers, riders, tri...
- [services/simulation/src/engine](../engine/CONTEXT.md) — Dependency — SimPy simulation environment orchestration, lifecycle state machine, and thread-...
- [services/simulation/src/events](../events/CONTEXT.md) — Dependency — Canonical Pydantic schemas for all simulation domain events and a factory that s...
- [services/simulation/src/geo](../geo/CONTEXT.md) — Dependency — Geospatial computation and routing services for the simulation engine
- [services/simulation/src/kafka](../kafka/CONTEXT.md) — Dependency — Kafka publishing layer for the simulation: producer, per-topic serializers, sche...
- [services/simulation/src/matching](../matching/CONTEXT.md) — Dependency — Driver-rider matching coordination: spatial driver discovery, composite scoring,...
- [services/simulation/src/metrics](../metrics/CONTEXT.md) — Dependency — In-process rolling-window metrics collection and OpenTelemetry export for simula...
- [services/simulation/src/trips](../trips/CONTEXT.md) — Dependency — SimPy coroutine orchestration for the end-to-end trip lifecycle, from driver dis...
