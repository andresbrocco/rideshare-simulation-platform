# CONTEXT.md — db

## Purpose

Persistence layer for the simulation service. Provides SQLite-backed ORM models for runtime state (agents, trips, route cache, metadata) and a pluggable checkpoint system that serializes and restores the full simulation world — enabling pause/resume, crash recovery, and container restart continuity.

## Responsibility Boundaries

- **Owns**: SQLAlchemy schema definitions, SQLite engine initialization, transaction/savepoint context managers, checkpoint creation and restoration logic (both SQLite and S3 backends)
- **Delegates to**: `repositories/` for all CRUD operations against individual tables; `agents.dna` for DNA deserialization during restore; `engine.SimulationEngine` for live runtime state during `save_from_engine` / `restore_to_engine`
- **Does not handle**: Kafka events, Redis publishing, or geospatial indexing (restored agents are re-registered into those systems by the checkpoint manager after loading)

## Key Concepts

- **Checkpoint type — graceful vs crash**: A checkpoint is "graceful" when no trips are in-flight at save time, and "crash" otherwise. On restore, crash checkpoints trigger automatic cancellation of all in-flight trips via `system/recovery_cleanup` to avoid inconsistent matching state. Downstream Kafka consumers are expected to deduplicate via `event_id`.
- **Dual backend via `get_checkpoint_manager`**: Backend is selected at startup from `settings.simulation.checkpoint_storage_type` (`"sqlite"` or `"s3"`). SQLite stores state relationally across four tables; S3 stores a single gzip-compressed JSON blob at `{prefix}/latest.json.gz`. Both implement the same interface (`save_from_engine`, `load_checkpoint`, `restore_to_engine`, `has_checkpoint`).
- **Schema format divergence**: The S3 checkpoint JSON stores `drivers` and `riders` at the top level, while the SQLite `load_checkpoint` returns them nested under an `"agents"` key. `restore_to_engine` in each class handles its own format accordingly.
- **RouteCache persistence**: OSRM route results (keyed as `{origin_h3}|{dest_h3}`) are checkpointed to SQLite to survive restarts and avoid redundant OSRM queries. Not persisted in the S3 backend (stored as an empty dict in the checkpoint structure).
- **`SimulationMetadata` table**: A generic key-value store used for all simulation-level metadata: `current_time`, `speed_multiplier`, `status`, `checkpoint_type`, `in_flight_trips`, `checkpoint_version`, `surge_multipliers`, `reserved_drivers`, `created_at`.
- **Naive UTC datetimes**: `utc_now()` deliberately strips timezone info to satisfy SQLite's plain TEXT datetime storage. All `datetime` columns in the schema are naive UTC.

## Non-Obvious Details

- During `restore_to_engine`, agents are constructed with `driver_repository=None` / `rider_repository=None` to suppress DB write-back during restore — the checkpoint is already the source of truth.
- Geospatial index (`registry_manager._driver_index`) and driver status registry must be manually repopulated during restore because those are in-memory structures not covered by SQLAlchemy persistence.
- Surge multipliers and reserved driver sets are persisted as JSON blobs in `SimulationMetadata` rather than separate tables — they are ancillary matching-server state that needs to survive restarts.
- `check_same_thread=False` is passed to the SQLite engine because FastAPI and SimPy run on separate threads that both access the same session factory.
- Schema version is seeded as `1.0.0` in `SimulationMetadata` at `init_database` time; version mismatch on restore logs a warning but does not abort.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
