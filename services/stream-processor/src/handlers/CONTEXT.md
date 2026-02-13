# CONTEXT.md — Handlers

## Purpose

Event handlers that consume Kafka messages and transform them into Redis pub/sub events for real-time frontend visualization. Each handler is responsible for a specific event type, with configurable processing strategies (pass-through or windowed aggregation).

## Responsibility Boundaries

- **Owns**: Kafka message deserialization, Pydantic validation, Redis channel routing, windowed aggregation logic
- **Delegates to**: Pydantic schemas for validation, metrics collector for error tracking, Redis client for publishing
- **Does not handle**: Kafka consumer management (handled by processor), Redis connection lifecycle (handled by main process), message ordering guarantees

## Key Concepts

**Pass-Through vs Windowed**: Handlers implement one of two strategies:
- Pass-through handlers (Trip, DriverStatus, Surge, Profiles, Rating) immediately emit critical events that cannot be delayed or aggregated
- Windowed handlers (GPS) buffer high-volume events and emit aggregated results on flush to reduce frontend message rate

**Aggregation Strategies** (GPS only):
- `latest`: Keep only the most recent position per entity within the window
- `sample`: Emit every Nth message per entity

**Channel Routing**: Handlers map event types to Redis pub/sub channels:
- `driver-updates`: GPS (drivers), driver status, driver profiles
- `rider-updates`: GPS (riders), rider profiles
- `trip-updates`: Trip state changes
- `surge_updates`: Surge pricing changes
- Ratings route to `driver-updates` or `rider-updates` based on ratee_type

## Non-Obvious Details

All handlers inherit from `BaseHandler` which defines the contract: `handle()` processes individual messages, `flush()` emits buffered state. The `is_windowed` property determines whether the processor should call flush periodically. Validation errors are logged but do not raise exceptions, allowing the stream processor to continue processing subsequent messages.
