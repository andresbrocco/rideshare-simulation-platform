# CONTEXT.md — DB

## Purpose

SQLite persistence layer for simulation state checkpoint and recovery. Enables graceful pause/resume across container restarts while maintaining exactly-once event semantics.

## Responsibility Boundaries

- **Owns**: SQLAlchemy ORM models, checkpoint creation/restoration, agent and trip persistence, route caching
- **Delegates to**: Repositories for CRUD operations, domain models for business logic validation
- **Does not handle**: Event publishing (Kafka), real-time state propagation (Redis), business logic (agents, trips, matching)

## Key Concepts

**Checkpoint Types**:
- `graceful` - Created after draining in-flight trips (zero active trips at checkpoint time)
- `crash` - Created with in-flight trips present; restoration cancels these trips to prevent duplicate events

**Two-Phase Recovery**: On dirty checkpoint restoration, in-flight trips are cancelled during recovery to ensure clean state and prevent duplicate event publishing to Kafka.

**Repository Pattern**: Generic `BaseAgentRepository` provides CRUD for drivers/riders. `TripRepository` manages trip state transitions with automatic timestamp updates.

**Location Storage**: Coordinates stored as comma-delimited strings (`"lat,lon"`) in SQLite for simplicity. DNA objects serialized as JSON.

## Non-Obvious Details

The checkpoint manager directly accesses SimPy environment state (`engine._env.now`) to capture simulation time, then recreates the environment with `initial_time` parameter during restoration. This preserves the exact simulation clock position.

Route cache uses H3 cell pairs as composite keys (`origin_h3|dest_h3`) and stores OSRM routing results to avoid repeated API calls for common routes.

The `utc_now()` utility returns timezone-naive datetimes representing UTC to match SQLite's TEXT datetime storage without timezone info.
