# CONTEXT.md — Simulation

## Purpose

The simulation service is a discrete-event simulation engine that generates realistic synthetic rideshare data. It orchestrates drivers and riders as autonomous agents interacting through a matching server, with all behavior parameterized by DNA (behavioral characteristics). The service runs alongside a FastAPI control panel in a unified process, with SimPy advancing simulation time in a background thread while the API handles real-time HTTP/WebSocket requests.

## Responsibility Boundaries

- **Owns**: Agent lifecycle (drivers, riders), trip state machine execution, simulation time management, state transitions (STOPPED, RUNNING, DRAINING, PAUSED), event generation for all domain entities
- **Delegates to**: Kafka (event publishing), Redis pub/sub (real-time frontend updates via stream-processor bridge), OSRM (route calculations), matching algorithm and surge pricing (matching server), geospatial operations (H3 indexing, zone assignment)
- **Does not handle**: Event persistence (delegated to data platform), frontend visualization logic, schema validation (handled by schema registry), direct Redis pub/sub publishing (routed through stream-processor)

## Key Concepts

**Agent DNA**: Immutable behavioral parameters assigned at agent creation that govern all decisions (acceptance rates, patience thresholds, service quality preferences). Distinct from profile attributes which can change via SCD Type 2 updates.

**Trip State Machine**: 10-state lifecycle with validated transitions. Terminal states (COMPLETED, CANCELLED) cannot transition further. STARTED state is special - once a rider is in the vehicle, cancellation is not permitted. Offer cycles allow OFFER_SENT → OFFER_EXPIRED/REJECTED → OFFER_SENT for sequential candidate matching.

**Two-Phase Pause**: RUNNING → DRAINING → PAUSED sequence ensures graceful shutdown. DRAINING state allows in-flight trips to complete (or force-cancels after 600s timeout) before checkpointing to PAUSED state, guaranteeing clean state recovery.

**Time Management**: TimeManager converts between SimPy's discrete event time (float seconds) and wall-clock datetime. Simulation speed is controlled by a multiplier (1x to 1024x) that throttles step() advancement via sleep() calls to achieve realtime pacing.

**Event Flow Architecture**: Simulation publishes exclusively to Kafka (source of truth). Stream-processor service consumes Kafka topics and republishes to Redis pub/sub channels. Frontend WebSocket subscribes to Redis channels. This eliminates duplicate events that occurred when simulation published directly to both systems.

**Kafka Reliability Tiers**: Tier 1 (Critical) events like trip state changes and payments use synchronous delivery confirmation. Tier 2 (High-Volume) events like GPS pings use fire-and-forget with error logging.

**Thread Coordination**: SimPy runs in a background thread while FastAPI runs on the main asyncio event loop. Agent spawning and trip matching are thread-safe via queues and deferred process creation at the start of each step() call.

## Non-Obvious Details

The simulation uses SimPy's discrete-event paradigm where agents yield control via timeout/event objects rather than running in parallel threads. All agent behavior is defined as generator functions (run() methods) that SimPy schedules cooperatively.

Settings are loaded via Pydantic with environment variable prefixes (SIM_*, KAFKA_*, REDIS_*, OSRM_*, API_*, CORS_*). The nested delimiter is double underscore (__) for hierarchical settings.

The main.py entry point performs complex dependency wiring: MatchingServer is created with placeholder dependencies, then AgentRegistryManager and NotificationDispatch are injected after creation. This circular dependency pattern is necessary because registry_manager needs matching_server reference and vice versa.

Agent processes are started lazily via _start_pending_agents() at the beginning of each step() to safely handle agents spawned from the API thread while simulation is running. The _process_started flag prevents duplicate process creation.

GPS ping intervals are naturally desynchronized across drivers because each driver starts its own _emit_gps_ping() process immediately upon spawn. No artificial jittering or global coordination is needed - the spawn times provide natural distribution.

Surge pricing updates every 60 simulated seconds via a dedicated SimPy process that calls matching_server.update_surge_pricing(). The calculation happens in the matching module but is triggered by the engine's periodic process.

Checkpoint/restore functionality uses SQLite to persist simulation state (environment time, agent states, trip states). Restoration requires validating state consistency and rebuilding in-memory references for all agents and trips.

The session_id (UUID) uniquely identifies each simulation run for distributed tracing across Kafka events. It is regenerated on reset() to distinguish separate simulation sessions in downstream analytics.

## Related Modules

- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Forms a data flow pipeline with simulation; consumes Kafka events produced by simulation and publishes to Redis pub/sub for frontend delivery
- **[services/frontend](../frontend/CONTEXT.md)** — Visualization partner; subscribes to simulation state via WebSocket and controls lifecycle via REST API
- **[schemas/kafka](../../schemas/kafka/CONTEXT.md)** — Defines the event contract; simulation produces events conforming to these JSON schemas
- **[data/sao-paulo](../../data/sao-paulo/CONTEXT.md)** — Provides geographic foundation; zones determine agent placement, surge pricing calculations, and spatial validation
- **[config](../../config/CONTEXT.md)** — Topic partitioning configuration ensures simulation events maintain ordering guarantees
