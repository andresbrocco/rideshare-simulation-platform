# CONTEXT.md — Repositories

## Purpose

Provides SQLAlchemy-backed persistence for simulation runtime state: drivers, riders, trips, and OSRM route cache. Each repository encapsulates all query and mutation logic for its entity, shielding the simulation engine from ORM details.

## Responsibility Boundaries

- **Owns**: All SQLite CRUD for drivers, riders, trips, and route cache entries; ORM-to-domain model translation for trips; savepoint-guarded checkpoint writes
- **Delegates to**: `src.db.schema` for ORM model definitions; `src.db.transaction` for savepoint context manager; `src.db.utils` for `utc_now()`; `trip.TripState` for valid state values
- **Does not handle**: Session lifecycle (callers manage `Session`); business logic (state transition validation lives in agent/engine layers); in-memory caching (only persists to SQLite)

## Key Concepts

- **BaseAgentRepository**: A `Generic[ModelT, DNAT]` base class shared by `DriverRepository` and `RiderRepository`. Requires DNA types to satisfy the `HasHomeLocation` Protocol (a structural subtype check, not inheritance). `DriverRepository` and `RiderRepository` are one-liner subclasses that set `model_class` and optionally `default_status`.
- **batch_upsert_with_state**: Used for checkpoint restores. Implements upsert as a delete-all then insert-all (simpler than true upsert for SQLite). Wrapped in a `savepoint` so the entire operation rolls back atomically if any insert fails — existing data is preserved on failure.
- **Route cache keying**: Routes are keyed by `"{origin_h3}|{dest_h3}"` (H3 cell IDs, not raw coordinates). This means cache hits are exact H3-pair matches, not proximity-based. TTL expiry is checked in Python on read, not enforced by a database constraint.

## Non-Obvious Details

- **Location stored as string**: Both agent and trip locations are persisted as `"lat,lon"` strings (e.g., `"-23.55,46.63"`), not as separate numeric columns. Callers split on `","` and cast to `float` when reading — `TripRepository._to_domain()` shows the pattern.
- **TripRepository does ORM translation; agent repositories do not**: `TripRepository.get()` returns a `TripDomain` domain object, while `BaseAgentRepository.get()` returns the raw ORM model. Callers of agent repositories interact directly with ORM objects.
- **`cancelled_by` Literal cast**: The ORM stores `cancelled_by` as a plain string. `_to_domain()` performs a runtime guard before casting to `Literal["rider", "driver", "system"]` — values outside that set become `None` rather than raising.
- **`RouteCacheRepository.load()` returns `None` for expired routes without deleting them**: Stale entries remain in the database until `clear_all()` or `invalidate()` is called explicitly. TTL enforcement is purely read-side.

## Related Modules

- [services/simulation/src/agents](../../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
