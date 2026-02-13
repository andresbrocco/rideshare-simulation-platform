# CONTEXT.md — Events

## Purpose

Defines the canonical Pydantic event schemas that represent all observable state changes in the rideshare simulation. These schemas serve as the contract between the simulation engine and downstream consumers (Kafka, data pipeline, frontend visualization).

## Responsibility Boundaries

- **Owns**: Event schema definitions with distributed tracing fields, event type enumerations, field validation rules
- **Delegates to**: Kafka serializers (`src.kafka`) for JSON serialization, trip state machine (`src.trips`) for state transition logic, agents (`src.agents`) for event emission
- **Does not handle**: Event persistence, schema registry registration, event routing logic, or business validation beyond field-level constraints

## Key Concepts

- **CorrelationMixin**: Base class providing distributed tracing fields (`session_id`, `correlation_id`, `causation_id`) inherited by all event types
- **Event Types**: Eight domain event schemas covering trip lifecycle (TripEvent), location tracking (GPSPingEvent), driver availability (DriverStatusEvent), dynamic pricing (SurgeUpdateEvent), post-trip feedback (RatingEvent), payments (PaymentEvent), and profile changes (DriverProfileEvent, RiderProfileEvent)
- **Route Progress Tracking**: Events include `route_progress_index` and `pickup_route_progress_index` fields for efficient frontend visualization updates without re-transmitting full route geometries
- **Immutable Events**: All events use `event_id` (UUID) as unique identifier; events are append-only facts representing point-in-time observations

## Non-Obvious Details

TripEvent contains 11 event_type literals matching the trip state machine (including trip.no_drivers_available) (trip.requested, trip.offer_sent, trip.matched, etc.). The offer_sequence field tracks retry attempts when drivers reject offers. Cancellation fields (cancelled_by, cancellation_reason, cancellation_stage) are only populated for trip.cancelled events.

GPS pings include both driver and rider locations. Rider pings during active trips carry trip_state to enable client-side filtering. The accuracy field simulates real GPS uncertainty.

Profile events (DriverProfileEvent, RiderProfileEvent) support both creation and updates via event_type discriminator, enabling SCD Type 2 tracking in the data warehouse.

## Related Modules

- **[src/agents](../agents/CONTEXT.md)** — Agents emit events using these schemas; event structure enables distributed tracing of agent actions
- **[src/trips](../trips/CONTEXT.md)** — TripExecutor emits trip lifecycle events using TripEvent, PaymentEvent, and GPSPingEvent schemas
- **[schemas/lakehouse/schemas](../../../../schemas/lakehouse/schemas/CONTEXT.md)** — Bronze layer PySpark schemas must match these Pydantic definitions for successful ingestion
