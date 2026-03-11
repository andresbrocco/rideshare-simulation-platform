# CONTEXT.md — Simulation

## Purpose

A self-contained Python service that runs a discrete-event rideshare simulation alongside a FastAPI HTTP/WebSocket control plane in a single process. It generates all synthetic rideshare events (trip lifecycle, driver movement, payments, ratings) for Sao Paulo and publishes them downstream to Kafka and Redis. It is the sole source of truth for simulation state.

## Responsibility Boundaries

- **Owns**: SimPy environment lifecycle, agent DNA and state machines, trip lifecycle transitions, fare calculation, surge pricing, geospatial driver matching, checkpoint persistence, Kafka event publication
- **Delegates to**: OSRM (route geometry), Kafka Schema Registry (event contract validation), Redis (real-time state fanout to stream-processor and WebSocket clients), SQLite/S3 (checkpoint storage)
- **Does not handle**: Consuming Kafka events (stream-processor owns that), Silver/Gold transformations (airflow/dbt own that), frontend rendering (control-panel owns that)

## Key Concepts

- **SimPy environment**: All agent processes are SimPy generator coroutines. The engine runs in a background `SimulationRunner` thread while FastAPI occupies the main thread. The `ThreadCoordinator` command queue bridges the two threads safely.
- **DNA**: Frozen Pydantic models encoding immutable behavioral parameters for driver and rider agents (risk tolerance, home zone, acceptance thresholds, etc.). DNA is generated once at spawn and never mutated.
- **Simulation time vs. wall time**: SimPy maintains its own virtual clock. The `speed_multiplier` (`SIM_SPEED_MULTIPLIER`) controls how fast simulated seconds pass relative to real seconds. RTR (Real-Time Ratio) is measured over a sliding window (`SIM_RTR_WINDOW_SECONDS`).
- **Agent modes**: Drivers and riders can be spawned in `immediate` mode (arrive in the simulation instantly) or `scheduled` mode (arrive according to configurable spawn rates). These are separate rate knobs (`SPAWN_DRIVER_*`, `SPAWN_RIDER_*`).
- **Trip state machine**: The `TripState` enum with `VALID_TRANSITIONS` enforces the full 10-state lifecycle (REQUESTED → OFFER_SENT → DRIVER_ASSIGNED → EN_ROUTE_PICKUP → AT_PICKUP → IN_TRANSIT → COMPLETED/CANCELLED), including offer expiry and rejection cycles. Terminal states (`COMPLETED`, `CANCELLED`) reject further transitions.
- **Arrival detection**: GPS-based using Haversine distance against `arrival_proximity_threshold_m` (default 50 m). Falls back to OSRM duration × `arrival_timeout_multiplier` (default 2×) if GPS check hasn't triggered.
- **Surge pricing**: A SimPy process (`SurgePricingCalculator`) periodically computes per-zone demand/supply ratios and updates the active surge multiplier. The multiplier is baked into the fare at request time and does not change once a trip is created.
- **Fare model**: Fixed formula: base fee $4.00 + $1.50/km + $0.25/min, minimum $8.00, then multiplied by the surge multiplier. Calculated once on trip request using estimated OSRM distance/duration; actual trip metrics do not revise it.
- **Matching ranking**: Candidate drivers are scored as a weighted sum of ETA, rating, and acceptance rate. Weights must sum to 1.0 (validated at startup via `MatchingSettings`).
- **Checkpoint**: Engine state (agents, trips, SimPy time) is serialized to SQLite locally or S3 in production. On startup, `try_restore_from_checkpoint()` is called if `SIM_RESUME_FROM_CHECKPOINT=true`.

## Non-Obvious Details

- The service runs **two threads**: the SimPy loop (`SimulationRunner`) and uvicorn (main thread). Commands from FastAPI are enqueued and consumed by the SimPy thread to avoid race conditions on shared state.
- `kafka-python` instrumentation is **intentionally omitted** from OpenTelemetry auto-instrumentation because the `kafka` top-level module shadows the local `src/kafka/` package. Only `confluent-kafka` is used.
- `main.py` has a **circular dependency workaround**: `MatchingServer` is constructed with `notification_dispatch=None` and `registry_manager=None`, then back-patched via attribute assignment after `AgentRegistryManager` and `NotificationDispatch` are created. This is load-bearing; order matters.
- Settings use **Pydantic validators** that raise at startup if credentials are missing (`API_KEY`, `REDIS_PASSWORD`, Kafka SASL credentials). The service will not start without them.
- The `KafkaSettings` validator raises on missing SASL credentials even when `security_protocol=PLAINTEXT`. In local dev the workaround is to pass dummy values for `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD` / `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO`.
- Port 8000 (container) maps to 8082 (host). `EXECUTION_API_SERVER_URL` in dependent services must use port 8082.
- An in-memory **user store** (`src/api/user_store.py`) provides a secondary credential layer on top of the shared API key. Passwords are stored exclusively as `bcrypt` hashes (`bcrypt==5.0.0`); plaintext is never retained. The store is populated at startup (provisioning phase) and treated as read-only thereafter, so no thread-locking is required.

## Related Modules

- [tools/great-expectations](../../tools/great-expectations/CONTEXT.md) — Shares Checkpointing & State Persistence domain (checkpoint)
