# CONTEXT.md — Repositories

## Purpose

Data access layer that provides CRUD operations for simulation entities (drivers, riders, trips, routes). Repositories abstract SQLAlchemy ORM operations and handle bidirectional translation between ORM models and domain models.

## Responsibility Boundaries

- **Owns**: Database queries, ORM-to-domain model translation, batch operations for checkpointing
- **Delegates to**: SQLAlchemy Session for transaction management, domain models for business logic
- **Does not handle**: Business logic, state validation, event publishing

## Key Concepts

**Generic Base Repository**: `BaseAgentRepository` uses Python generics (`Generic[ModelT, DNAT]`) to share CRUD logic between `DriverRepository` and `RiderRepository`. The `HasHomeLocation` protocol ensures DNA types are compatible.

**Domain Model Translation**: `TripRepository._to_domain()` converts SQLAlchemy ORM models (flat database schema with string-encoded locations) into rich domain models (`TripDomain` with tuple coordinates and enum states). This separation allows the domain layer to remain database-agnostic.

**Checkpoint Upsert**: `batch_upsert_with_state()` uses savepoints to atomically replace all agent records during checkpoint restoration. Delete-then-insert pattern is simpler than true upsert for SQLite.

**H3-Based Route Cache**: `RouteCacheRepository` stores OSRM routes keyed by H3 cell pairs (`origin_h3|dest_h3`). TTL-based expiration (default 30 days) handles stale routes without manual invalidation.

## Non-Obvious Details

Location storage uses comma-separated strings (`"lat,lon"`) in the database but exposes tuples (`(lat, lon)`) at the API level. This keeps the SQLite schema simple while maintaining type safety in Python.

The `offer_sequence` field in trips tracks how many drivers have been offered the trip. It increments on each `OFFER_SENT` state transition and is used for analytics on match efficiency.

Route cache uses SQLite's `INSERT ... ON CONFLICT DO UPDATE` (upsert) to avoid duplicate key errors when pre-populating from persistent storage.

## Related Modules

- **[services/simulation/src/db](../CONTEXT.md)** — Defines ORM models that repositories query and manipulate
- **[services/simulation/src/matching](../../matching/CONTEXT.md)** — Uses repositories to persist trip state and cache routes for driver ranking
