# CONTEXT.md — Trips

## Purpose

Orchestrates the complete trip lifecycle from driver-rider match through completion or cancellation. The `TripExecutor` coordinates multi-step async workflows (pickup drive, wait, trip drive, completion) while managing state transitions, route planning with retries, GPS pings, and event publishing.

## Responsibility Boundaries

- **Owns**: Trip execution workflow (drive-to-pickup, wait-for-rider, start-trip, drive-to-destination, complete-trip), route fetching with exponential backoff retry, GPS ping emission during drives, proximity-based arrival detection, cancellation cleanup
- **Delegates to**: `OSRMClient` for route planning, `Trip` model for state machine validation, `DriverAgent`/`RiderAgent` for status updates, `KafkaProducer` for event publishing, `MatchingServer` for active trip tracking
- **Does not handle**: Trip state machine logic (owned by `Trip` model), driver-rider matching (owned by `MatchingServer`), offer management and timeouts (owned by `MatchingServer`)

## Key Concepts

**TripExecutor**: SimPy generator-based coordinator that executes as a simulated process. Must be started from the SimPy thread (queued via `MatchingServer._pending_trip_executions`). Not used for puppet drivers (API-controlled).

**Proximity-based arrival**: Instead of purely time-based drive simulation, checks GPS distance to destination at each interval. When within `arrival_proximity_threshold_m`, the drive completes early. Prevents overshooting destinations.

**Route progress tracking**: Maintains `route_progress_index` and `pickup_route_progress_index` on the `Trip` model for frontend visualization of driver position along the route geometry.

**Error handling tiers**: Distinguishes `PermanentError` (no retry, e.g., no route found) from `TransientError` (retry with backoff, e.g., OSRM timeout). Uses `_cleanup_failed_trip()` for non-terminal failures.

**Test flags**: Constructor accepts `rider_boards`, `rider_cancels_mid_trip` for deterministic testing of cancellation scenarios without randomness.

## Non-Obvious Details

**Why separate event emission methods**: `_emit_trip_event()` for state transitions, `_emit_payment_event()` for payments, `_emit_gps_ping()` for location updates. Each has different schema requirements and Kafka topics (trips, payments, gps-pings).

**Why route stored on Trip model**: Routes (`route`, `pickup_route`) are marked as "not persisted to database" in Trip model but stored in memory for WebSocket visualization. Progress indices enable efficient incremental updates without resending entire route.

**Why Redis publisher optional**: Only used for legacy direct Redis publishing. Current architecture has TripExecutor emit to Kafka only; separate `stream-processor` service consumes Kafka and publishes to Redis pub/sub for frontend.

**Why completion stats calculated here**: Trip timing metrics (pickup_time, wait_time, trip_duration) are derived from Trip timestamps and recorded to driver/rider statistics before calling `complete_trip()` on agents.

**Why STARTED state cannot cancel**: Trip state machine forbids cancelling once rider is in vehicle. See `VALID_TRANSITIONS` in `trip.py` - STARTED only transitions to COMPLETED.
