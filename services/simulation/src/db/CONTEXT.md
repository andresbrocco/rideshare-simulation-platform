# CONTEXT.md — DB

## Purpose

Persistence layer for simulation state checkpoint and recovery with dual storage backends. Enables graceful pause/resume across container restarts while maintaining exactly-once event semantics.

## Storage Backends

- **S3** (default in Docker): Stores gzip-compressed JSON in S3-compatible storage (MinIO locally, AWS S3 in production). Configured via `SIM_CHECKPOINT_STORAGE_TYPE=s3`. Supports full save/restore and enables local-to-cloud data migration.
- **SQLite** (fallback): Uses SQLAlchemy ORM models for local file-based persistence. Configured via `SIM_CHECKPOINT_STORAGE_TYPE=sqlite`. Used when S3 is not available (e.g., `core` profile without MinIO).

## Responsibility Boundaries

- **Owns**: Checkpoint creation/restoration (S3 and SQLite), SQLAlchemy ORM models, agent and trip persistence, route caching, transaction management
- **Delegates to**: Repositories for CRUD operations, domain models for business logic validation
- **Does not handle**: Event publishing (Kafka), real-time state propagation (Redis), business logic (agents, trips, matching)

## Key Concepts

**Checkpoint Types**:
- `graceful` - Created after draining in-flight trips (zero active trips at checkpoint time)
- `crash` - Created with in-flight trips present; restoration cancels these trips to prevent duplicate events

**Two-Phase Recovery**: On dirty checkpoint restoration, in-flight trips are cancelled during recovery to ensure clean state and prevent duplicate event publishing to Kafka.

**Transaction Management**: Explicit `transaction()` and `savepoint()` context managers ensure atomic operations. Checkpoints use transactions to guarantee all-or-nothing persistence.

**Location Storage**: Coordinates stored as comma-delimited strings (`"lat,lon"`) in SQLite for simplicity. DNA objects serialized as JSON.

## Non-Obvious Details

The checkpoint manager directly accesses SimPy environment state (`engine._env.now`) to capture simulation time, then recreates the environment with `initial_time` parameter during restoration. This preserves the exact simulation clock position.

Route cache uses H3 cell pairs as composite keys (`origin_h3|dest_h3`) and stores OSRM routing results to avoid repeated API calls for common routes.

The `utc_now()` utility returns timezone-naive datetimes representing UTC to match SQLite's TEXT datetime storage without timezone info.

The `save_from_engine()` method captures full runtime state including matching server internals (surge multipliers, reserved drivers) for complete restoration.

## Related Modules

- **[src/db/repositories](repositories/CONTEXT.md)** — Repository layer that provides CRUD operations using ORM models defined here
- **[src/engine](../engine/CONTEXT.md)** — Simulation engine that triggers checkpoint saves and restores state during initialization
- **[src/agents](../agents/CONTEXT.md)** — Agent domain models that are persisted to database via repositories
