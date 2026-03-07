# CONTEXT.md — Events

## Purpose

Defines the canonical Pydantic schemas for all domain events emitted by the simulation engine, plus a factory that stamps every event with distributed tracing fields. This module is the schema contract between the simulation and downstream consumers (Kafka, stream processor, frontend).

## Responsibility Boundaries

- **Owns**: Event schema definitions, correlation/causation field population, causation-chain mutation on `Trip` objects
- **Delegates to**: `core.correlation.get_current_session_id()` for session ID resolution; callers (agents, engine) for Kafka publishing
- **Does not handle**: Serialization to Kafka (handled by `src/kafka`), routing or topic assignment, or any event consumption logic

## Key Concepts

- **CorrelationMixin**: Base mixin added to every event carrying three distributed-tracing fields — `session_id` (simulation run), `correlation_id` (primary business key, e.g. `trip_id`), and `causation_id` (ID of the event that triggered this one). These fields enable end-to-end tracing across the entire pipeline without a dedicated tracing sidecar.
- **Causation chaining**: `EventFactory.create_for_trip()` reads `trip.last_event_id` as the `causation_id` and then, when `update_causation=True`, overwrites `trip.last_event_id` with the new event's UUID. This mutates the `Trip` object as a side effect of event creation, forming an ordered causal chain for the entire trip lifecycle.
- **route_progress_index / pickup_route_progress_index**: Integer indices into pre-computed OSRM route geometry arrays. Sent in `TripEvent` and `GPSPingEvent` to allow the frontend to advance position along the route without re-querying geometry on every GPS ping.

## Non-Obvious Details

- `EventFactory.create` accepts a pre-fetched `session_id` parameter to avoid a context-variable read on every event construction in hot simulation loops. Callers that emit many events in a tight loop should fetch the session ID once and pass it down.
- `TripEvent` carries optional `route` and `pickup_route` fields (full geometry) alongside `route_progress_index`. The full geometry is sent once (on assignment / en-route events) and subsequent GPS pings only send the index, reducing payload size.
- `DriverProfileEvent` and `RiderProfileEvent` include PII fields (`email`, `phone`) that are masked by the logging filter before reaching Loki — but they are stored unmasked in Kafka and Bronze layer intentionally, as the masking is a logging-only concern.
- `RatingEvent.current_rating` and `rating_count` represent the rolling aggregate state *after* the new rating is applied, not before. This means the event is self-contained for downstream Silver/Gold models without needing a join back to a ratings table.
- The `__init__.py` exports nothing — consumers import directly from `events.schemas` and `events.factory`.

## Related Modules

- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
