# CONTEXT.md — Simulation src

## Purpose

Top-level source package for the simulation service. Contains the application entry point, cross-cutting domain models, and the Pydantic settings hierarchy. Sub-packages implement the major subsystems (engine, agents, matching, geo, api, db, events, etc.), which are wired together here in `main.py`.

## Responsibility Boundaries

- **Owns**: Application bootstrap and dependency wiring; domain models shared across subsystems (`Trip`, `FareBreakdown`, `Payment`, `Rating`); the unified Pydantic settings tree
- **Delegates to**: Sub-packages for all subsystem logic (`engine`, `agents`, `matching`, `geo`, `api`, `db`, `kafka`, `redis_client`, `sim_logging`, `metrics`, `api.middleware`)
- **Does not handle**: Individual agent behavior, Kafka serialization, geospatial indexing, or HTTP route definitions — each lives in its own sub-package

## Key Concepts

- **SimulationRunner**: Thin wrapper that advances the SimPy environment in a background thread, calling `engine.step(10)`. Also keeps stepping during `DRAINING` state so in-flight trips can complete before pausing.
- **Unified process model**: FastAPI (uvicorn) runs on the main thread; the SimPy loop runs on a daemon thread. Both share the same in-process object graph (engine, registries, producers). There is no IPC boundary between the HTTP layer and the simulation.
- **Deferred wiring**: Several components are constructed with `None` placeholders and patched after all objects exist (e.g., `matching_server._notification_dispatch`, `matching_server._registry_manager`, `matching_server._surge_calculator`, `engine._agent_factory`). This breaks circular construction dependencies but means the objects are not fully functional until `main()` completes all wiring steps.
- **TripState machine** (`trip.py`): 10-state enum with `VALID_TRANSITIONS` dict enforcing legal edges. `OFFER_SENT` ↔ `OFFER_EXPIRED` / `OFFER_REJECTED` allows retry cycles before terminal states. `offer_sequence` increments on each `OFFER_SENT` transition to track how many drivers were tried.
- **Fare locking**: Fare is calculated once at request time from the OSRM-estimated distance/duration and the current surge multiplier. It does not change when the actual trip differs from the estimate.
- **Payment split**: `Payment` auto-computes `platform_fee_amount` and `driver_payout_amount` via a `model_validator`; platform takes 25% by default.

## Non-Obvious Details

- `KafkaSettings`, `RedisSettings`, and `APISettings` all fail at startup if required credentials are absent (validated via `model_validator`). This is intentional — the service refuses to start silently without its external dependencies configured.
- `MatchingSettings` validates that the three ranking weights (`eta`, `rating`, `acceptance`) sum to 1.0 (±0.01 tolerance) in `__init__`, not in a Pydantic validator, because it needs access to multiple fields simultaneously after construction.
- OTel SDK must be initialized (`init_otel_sdk()`) before `create_app()` so FastAPI auto-instrumentation picks up the already-configured providers. Reversing this order would lose traces from the FastAPI layer.
- The `SIM_DB_PATH` environment variable controls the SQLite database path used for both simulation state and checkpointing in local mode. In production, checkpoint storage can be switched to S3 via `SIM_CHECKPOINT_STORAGE_TYPE=s3`.
- `Trip.route` and `Trip.pickup_route` carry GeoJSON coordinate arrays for the frontend visualization but are intentionally not persisted to the database (noted in the field comment).

## Related Modules

- [services/simulation/src/agents](agents/CONTEXT.md) — Dependency — SimPy agent lifecycle, DNA behavioral models, and Kafka event emission for drive...
- [services/simulation/src/api](api/CONTEXT.md) — Dependency — FastAPI application layer bridging the SimPy simulation engine to HTTP control endpoints, WebSocket streaming, session lifecycle, bcrypt user store, and role-based access control...
- [services/simulation/src/db](db/CONTEXT.md) — Dependency — SQLite ORM schema and pluggable checkpoint system for saving and restoring full ...
- [services/simulation/src/engine](engine/CONTEXT.md) — Dependency — SimPy simulation environment orchestration, lifecycle state machine, and thread-...
- [services/simulation/src/geo](geo/CONTEXT.md) — Dependency — Geospatial computation and routing services for the simulation engine
- [services/simulation/src/kafka](kafka/CONTEXT.md) — Dependency — Kafka publishing layer for the simulation: producer, per-topic serializers, sche...
- [services/simulation/src/matching](matching/CONTEXT.md) — Dependency — Driver-rider matching coordination: spatial driver discovery, composite scoring,...
- [services/simulation/src/metrics](metrics/CONTEXT.md) — Dependency — In-process rolling-window metrics collection and OpenTelemetry export for simula...
- [services/simulation/src/redis_client](redis_client/CONTEXT.md) — Dependency — Redis pub/sub publication and state snapshot management for real-time frontend v...
- [services/simulation/src/sim_logging](sim_logging/CONTEXT.md) — Dependency — Structured, context-enriched logging with PII masking and thread-local field inj...
