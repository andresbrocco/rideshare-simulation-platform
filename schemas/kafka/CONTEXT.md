# CONTEXT.md — Kafka Schemas

## Purpose

Defines the formal JSON Schema (draft/2020-12) contracts for all Kafka event topics produced by the simulation and consumed by downstream services (stream processor, bronze ingestion). These schemas are the canonical source of truth for inter-service event contracts.

## Responsibility Boundaries

- **Owns**: Field names, types, required fields, enumerated values, and validation constraints for every event published to Kafka
- **Delegates to**: Kafka Schema Registry for runtime enforcement; consuming services for business logic applied to validated events
- **Does not handle**: Topic routing, partitioning strategy, or serialization format (Avro/JSON decision lives in Schema Registry config)

## Key Concepts

- **Event envelope**: Every schema includes a shared tracing envelope — `session_id` (simulation run identifier), `correlation_id` (primary entity ID, e.g., trip_id), and `causation_id` (ID of the upstream event that triggered this one). These fields are nullable to allow events emitted outside a simulation session.
- **Trip lifecycle events**: `trip_event.json` covers the full state machine via `event_type` enum — from `trip.requested` through terminal states (`trip.completed`, `trip.cancelled`, `trip.no_drivers_available`). Route geometry is carried inline on the event rather than fetched separately.
- **Profile vs. state events**: Profile schemas (`driver_profile_event`, `rider_profile_event`) represent entity creation/update and carry PII fields (name, email, phone, home_location). Status/transactional schemas (`driver_status_event`, `trip_event`, `payment_event`, `rating_event`, `surge_update_event`, `gps_ping_event`) carry operational state.
- **Offer sequencing**: `trip_event` includes `offer_sequence` (integer starting at 1), tracking how many driver offers have been sent for a given trip request before a driver accepts or the offers expire.

## Non-Obvious Details

- `behavior_factor` in `rider_profile_event` is **only present on `rider.created` events**, not on `rider.updated`. It encodes the rider agent's DNA-derived behavioral parameter and is excluded from update events because it is immutable after creation.
- Coordinates are encoded as `[latitude, longitude]` arrays (not GeoJSON `[longitude, latitude]` order). All downstream consumers must account for this ordering.
- `surge_update_event` encodes `previous_multiplier` and `new_multiplier` with a minimum of `1.0`, meaning baseline (no-surge) pricing is represented as `1.0`, not `0`.
- `payment_event` expresses `platform_fee_percentage` as a decimal fraction (`0.0`–`1.0`), not a percentage integer. `driver_payout_amount` is the already-computed net payout, not derived by consumers.
- `gps_ping_event` is entity-agnostic: `entity_type` distinguishes driver vs. rider pings on a shared topic rather than having separate topics per entity type.
- `route` and `pickup_route` in `trip_event` store route geometry as arrays of `[lat, lon]` pairs; `route_progress_index` and `pickup_route_progress_index` allow downstream consumers to reconstruct the driver's current position along the route without re-querying OSRM.

## Related Modules

- [services/simulation/tests/kafka](../../services/simulation/tests/kafka/CONTEXT.md) — Reverse dependency — Consumed by this module
