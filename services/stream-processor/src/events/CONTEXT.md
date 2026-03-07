# CONTEXT.md — Events

## Purpose

Defines Pydantic schemas used by the stream processor to validate and parse incoming Kafka events before fan-out to Redis and downstream consumers. These schemas mirror the simulation's event contracts and serve as the deserialization boundary for all inbound event types.

## Responsibility Boundaries

- **Owns**: Schema definitions and field-level validation rules for each event type consumed by the stream processor
- **Delegates to**: Handlers in `src/handlers/` for business logic after deserialization; the simulation service for event production and origination
- **Does not handle**: Event routing, Redis publishing, or Kafka consumer lifecycle

## Key Concepts

- **TripEvent**: Covers the full trip lifecycle (requested → completed/cancelled) and carries inline route geometry (`route`, `pickup_route`) and progress indices — it is not limited to state transition metadata alone.
- **SurgeUpdateEvent**: Carries the raw demand inputs (`available_drivers`, `pending_requests`) that drove the surge recalculation, along with the `calculation_window_seconds` context window.
- **DriverStatusEvent.trigger**: A free-text field describing what caused the status change (e.g., "trip_completed", "manual_offline") — not validated against an enum.

## Non-Obvious Details

- `RatingEvent` is defined in `schemas.py` but intentionally excluded from `__init__.py` exports. It is not currently consumed by the stream processor's handler pipeline and exists as a forward-looking schema stub.
- `RiderProfileEvent.behavior_factor` is optional and carries no validation range constraint. It encodes the rider's DNA behavior modifier from the simulation but may be absent if the rider was created before this field was introduced.
- `TripEvent.driver_id` is nullable to support terminal events like `trip.no_drivers_available` and `trip.cancelled` that may fire before driver assignment.
- Locations are typed as `tuple[float, float]` (latitude, longitude order) — the tuple is ordered `(lat, lon)`, consistent with the simulation's H3 and Haversine conventions.

## Related Modules

- [services/stream-processor/src/handlers](../handlers/CONTEXT.md) — Reverse dependency — Provides BaseHandler, DriverProfileHandler, DriverStatusHandler (+5 more)
