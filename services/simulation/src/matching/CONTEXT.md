# CONTEXT.md — Matching

## Purpose

Coordinates all driver-rider matching logic within the simulation: finding nearby drivers, scoring and ranking candidates, running the offer cycle, tracking offer timeouts, computing surge pricing, and maintaining thread-safe registries of driver state and location.

## Responsibility Boundaries

- **Owns**: Trip lifecycle from `trip.requested` through `trip.driver_assigned`; offer cycle state; surge multiplier calculation; driver spatial indexing; driver status registry; agent registry facade
- **Delegates to**: `trips.trip_executor` (en-route and on-trip execution after assignment); `geo.osrm_client` (real-world ETA computation); `events.factory` / `kafka.producer` (Kafka event emission); `redis_client.publisher` (real-time state propagation); `puppet.drive_controller` (movement of puppet drivers)
- **Does not handle**: Trip execution after driver assignment, route geometry rendering, Kafka schema serialization, agent DNA definition

## Key Concepts

**MatchingServer** — Central coordinator. Exposes `request_match()` (async, called from `RiderAgent`) and `send_offer_cycle()` (sync, runs within SimPy thread). Maintains `_active_trips`, `_reserved_drivers`, `_retry_queue`, and per-trip `_pending_offer_candidates` for multi-driver offer cascades.

**Offer cycle** — Offers are sent to ranked drivers one at a time. The accept/reject decision is pre-computed at offer time (`_compute_offer_decision`) but applied after a Gaussian delay (`_deferred_offer_response` SimPy process) that simulates driver think time. If the delay exceeds `offer_timeout_seconds`, the `OfferTimeoutManager` fires first and expires the offer. Rejected offers continue to the next candidate via `_continue_deferred_offer_cycle`.

**Composite scoring** — `rank_drivers()` ranks candidates using a weighted score of normalized ETA (lower is better, inverted), driver rating (1–5 normalized to 0–1), and DNA acceptance rate. Weights are configurable via `Settings.matching`.

**Driver reservation** — A driver entering the offer cycle is added to `_reserved_drivers` to prevent double-booking. Reservation is cleared on acceptance, rejection, timeout, or trip completion. A safety net in `complete_trip()` always clears the reservation.

**OfferTimeoutManager** — A pure SimPy timer component. Spawns a timeout process per offer; if the timer fires before the driver responds, it calls `MatchingServer._handle_offer_expired` (all side effects stay in `MatchingServer`). Cancels cleanly via `simpy.Interrupt` when an offer is cleared before expiry.

**DriverGeospatialIndex** — H3-based spatial index (resolution 9, ~174 m edge length) for O(1) driver lookups by hex cell. Uses progressive ring expansion starting at k=5, doubling outward only if no candidates are found. Maintains a parallel `_driver_status` dict to filter by status inside the lock without touching the registry.

**DriverRegistry** — Maintains denormalized status counters (`_status_counts`) and per-zone status counters (`_zone_status_counts`) for O(1) metric reads. Used by `SurgePricingCalculator` to check available driver counts without iterating agents.

**AgentRegistryManager** — Unified facade over `DriverGeospatialIndex`, `DriverRegistry`, and the raw `_agents` dict in `MatchingServer`. Ensures multi-registry updates are atomic under a single lock. Agent lifecycle events (`driver_went_online`, `driver_went_offline`, `driver_location_updated`, `driver_status_changed`) fan out to all registries in one call.

**SurgePricingCalculator** — SimPy process that recalculates surge every `update_interval_seconds`. Formula: if `pending/available <= 1.0` → multiplier 1.0; linear up to 2.5× cap at ratio ≥ 3.0. Publishes `surge_updates` Kafka events only when the multiplier changes. Pending request counts are incremented by `MatchingServer.request_match` and decremented on match, cancellation, or no-drivers.

**NotificationDispatch** — Thin router that maps trip state changes to the correct `on_*` callbacks on `DriverAgent` or `RiderAgent`. Does not own trip state; it reads `TripState` to decide which callbacks to invoke.

## Non-Obvious Details

**Thread boundary for SimPy process creation.** `env.process()` is not thread-safe and must only be called from the SimPy thread. Any code path that originates from the FastAPI/asyncio thread (e.g., `_start_trip_execution`, `send_offer`) queues work into `_pending_trip_executions`, `_pending_deferred_offers`, or `_pending_offer_timeouts`. The SimPy thread drains these queues each tick via `start_pending_trip_executions()`.

**OSRM candidate limit.** Spatial search returns up to unlimited candidates, but only the top 15 by haversine distance receive OSRM route fetches. This avoids hammering OSRM with parallel requests for low-probability far-away drivers.

**Retry queue for no-drivers.** When no candidate is found (or all offers are exhausted), the trip is NOT immediately cancelled. It is placed in `_retry_queue` with a future SimPy time. `retry_pending_matches()` is called periodically from the engine to re-attempt matching. A guard (`_retry_in_progress`) prevents concurrent coroutines from running parallel retry loops.

**`driving_closer_to_home` is eligible for matching.** `find_nearby_drivers` uses `status_filter={"available", "driving_closer_to_home"}`, so a driver returning home will accept intercepts if the offer scores well.

**Puppet driver special path.** Puppet drivers (controlled externally via the API) receive offers but their acceptance is handled via a different code path through `PuppetDriveController` rather than the DNA-based `_compute_offer_decision`. The `_pending_offer_candidates` dict preserves remaining candidates so the offer cycle can continue if the puppet rejects.

**Completed/cancelled trip history is bounded.** `_completed_trips` and `_cancelled_trips` are `deque(maxlen=...)` controlled by `Settings.matching.max_trip_history` to prevent unbounded memory growth. Running accumulators (`_stats_total_fare`, etc.) are maintained alongside them so aggregate stats remain accurate even after old trips roll off.

## Related Modules

- [services/simulation/src](../CONTEXT.md) — Reverse dependency — Provides main, SimulationRunner, Settings (+8 more)
- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
