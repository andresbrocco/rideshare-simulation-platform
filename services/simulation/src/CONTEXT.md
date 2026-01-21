# CONTEXT.md — Simulation Source Root

## Purpose

Root package for the rideshare simulation engine. Orchestrates a discrete-event simulation (SimPy) that models drivers and riders interacting in Sao Paulo, generating realistic synthetic data for downstream analytics. Runs as a unified service combining the simulation loop with a FastAPI control panel API.

## Responsibility Boundaries

- **Owns**: Simulation lifecycle (start/stop/pause), agent spawning and behavior, trip state machine execution, matching logic, surge pricing calculation, event publishing (Kafka), state snapshots (Redis/SQLite)
- **Delegates to**: OSRM for route calculations, Kafka for event streaming, Redis for real-time pub/sub, SQLite for persistence, frontend for visualization
- **Does not handle**: Data transformation (delegated to Spark/DBT), long-term storage (delegated to lakehouse), business intelligence (delegated to Looker/Superset)

## Key Concepts

- **Agent DNA**: Immutable behavioral parameters assigned at agent creation (acceptance rates, patience thresholds, service quality). Profile attributes (vehicle info, contact) can change via SCD Type 2 updates.
- **Trip State Machine**: 10-state validated FSM (REQUESTED → OFFER_SENT → MATCHED → DRIVER_EN_ROUTE → DRIVER_ARRIVED → STARTED → COMPLETED). Offers can expire/be rejected and cycle to next driver. STARTED state cannot be cancelled (rider in vehicle).
- **Surge Pricing**: Per-zone multipliers (1.0x-2.5x) calculated every 60 simulated seconds based on supply/demand ratio.
- **Two-Phase Pause**: Graceful pause drains in-flight trips before checkpointing to ensure clean state recovery.
- **Event Flow**: Simulation publishes exclusively to Kafka (source of truth). Separate stream-processor service consumes Kafka and publishes to Redis pub/sub for real-time visualization. No direct Redis publishing from simulation to eliminate duplicate events.

## Non-Obvious Details

- **Unified Service Architecture**: FastAPI runs on main thread while SimPy simulation runs in background thread (`SimulationRunner`). Shared SimPy environment ensures thread-safe coordination.
- **Module Import Pattern**: All imports use absolute paths from `src/` (e.g., `from agents.driver_agent import DriverAgent`), not relative imports.
- **Kafka Reliability Tiers**: Tier 1 (trip state, payments) uses synchronous delivery confirmation; Tier 2 (GPS pings, driver status) uses fire-and-forget with error logging.
- **GPS-Based Arrival**: Driver arrival at pickup/dropoff is detected via proximity threshold (50m default) rather than route completion, with timeout fallback based on OSRM duration multiplier.
- **Circular Dependencies**: Some modules have circular references resolved via late binding (e.g., `MatchingServer` initialized with `None` for `notification_dispatch` and `registry_manager`, then wired after creation).
