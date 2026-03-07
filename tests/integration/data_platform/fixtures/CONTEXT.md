# CONTEXT.md — Fixtures

## Purpose

Event factory functions that produce synthetic Kafka event payloads for integration tests. Each module generates dictionaries matching a specific event schema (gps_ping_event, trip_event, driver_status_event, driver_profile_event, rider_profile_event) so tests can inject controlled data into the data pipeline without running the full simulation.

## Responsibility Boundaries

- **Owns**: Constructing valid, schema-conformant event dictionaries with realistic default values anchored to São Paulo
- **Delegates to**: Callers (conftest fixtures, test functions) to decide how many events to produce and what fields to override
- **Does not handle**: Kafka publishing, Bronze ingestion, schema validation, or any I/O

## Key Concepts

- **Lifecycle sequences**: `generate_trip_lifecycle` produces the canonical 6-state happy path (`trip.requested` → `trip.matched` → `trip.driver_en_route` → `trip.driver_arrived` → `trip.started` → `trip.completed`) with realistic inter-state time deltas baked in.
- **SCD Type 2 pairs**: `generate_driver_profile_with_update` and `generate_rider_profile_with_update` emit a `created` event followed by an `updated` event with modified fields. These are the primary fixtures for testing SCD Type 2 dimension handling in the Gold layer.
- **`**kwargs` override pattern**: All single-event generators accept `**kwargs` that are merged into the event dict via `event.update(kwargs)`. This is how tests inject invalid or edge-case field values without a separate factory variant.

## Non-Obvious Details

- `correlation_id` defaults to `trip_id` in trip and GPS events when not explicitly provided — this mirrors the production simulation's correlation convention and is load-bearing for pipeline lineage tests.
- `behavior_factor` is schema-present only in `rider.created` events. The rider factory silently sets it to `None` for `rider.updated` events regardless of what the caller passes, enforcing the schema constraint in the fixture layer.
- `generate_multi_driver_gps_pings` is annotated with test case reference `FJ-002` in its docstring, indicating it was purpose-built for a specific high-volume ingestion scenario.
- The GPS sequence generator clamps coordinates to the São Paulo bounding box during simulated movement to prevent geospatially invalid test data drifting out of bounds.
- Driver status transitions in `generate_driver_status_transitions` space events exactly 5 minutes apart regardless of the transition type — tests relying on duration-based metrics should account for this fixed interval.

## Related Modules

- [tests/integration](../../CONTEXT.md) — Reverse dependency — Provides docker_compose, load_credentials, reset_all_state (+7 more)
