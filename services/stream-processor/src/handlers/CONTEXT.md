# CONTEXT.md — Handlers

## Purpose

Event-type-specific processors that consume raw Kafka message bytes, validate them against Pydantic schemas, and produce `(channel, event)` tuples for publication to Redis pub/sub channels. Each handler encapsulates the routing and aggregation logic for a single Kafka event type.

## Responsibility Boundaries

- **Owns**: Schema validation per event type, Redis channel routing decisions, GPS windowed aggregation state, event payload mutation (e.g., injecting `event_type` for the frontend)
- **Delegates to**: `events.schemas` for Pydantic model definitions; `metrics` collector for recording validation errors
- **Does not handle**: Kafka consumption, Redis publishing, or inter-event correlation — those are the caller's responsibility

## Key Concepts

**Pass-through vs. windowed handlers**: All handlers inherit `BaseHandler`, which defines two modes. Pass-through handlers (most of them) return `(channel, event)` tuples immediately from `handle()` and return empty lists from `flush()`. The windowed handler (`GPSHandler`) returns an empty list from `handle()`, accumulating state internally, and only emits events during `flush()`, which the stream processor calls on a periodic timer. The `is_windowed` property distinguishes them.

**GPS aggregation strategies**: `GPSHandler` supports two strategies. `"latest"` keeps only the most recent GPS ping per entity within a window, discarding all intermediate positions. `"sample"` emits every Nth ping per entity. Both strategies exist to reduce message rate to the frontend under high agent counts. The default is `"latest"` with a 100 ms window.

**Channel routing**: Handlers route to named Redis channels — `driver-updates`, `rider-updates`, `trip-updates`, `surge_updates`. `GPSHandler` inspects `entity_type` in the event to choose between `driver-updates` and `rider-updates`. `RatingHandler` inspects `ratee_type` for the same decision.

## Non-Obvious Details

- `RatingHandler` mutates the validated event dict by injecting `"event_type": "rating_update"` before emitting. This is the only handler that augments the payload; the others emit the Pydantic model dump unchanged.
- When `GPSHandler` flushes, it clears `window_state` entirely. There is no carry-over of unseen entities between windows — if an entity sends no pings in a window, it emits nothing.
- Validation failures (both `ValidationError` and `json.JSONDecodeError`) are handled identically: log a warning, record a metric, and return an empty list. Invalid messages are silently dropped rather than sent to a DLQ from within the handler.
- `surge_updates` uses an underscore whereas all other channels use hyphens (`driver-updates`, `rider-updates`, `trip-updates`). This inconsistency is present in the current code.

## Related Modules

- [services/stream-processor/src](../CONTEXT.md) — Reverse dependency — Provides StreamProcessor, Settings, get_settings (+4 more)
- [services/stream-processor/src](../CONTEXT.md) — Shares Redis and Real-Time State domain (pass-through handler, windowed handler)
- [services/stream-processor/src/events](../events/CONTEXT.md) — Dependency — Pydantic schemas for validating and deserializing Kafka events at the stream pro...
