# CONTEXT.md — Matching

## Purpose

Orchestrates the driver-rider matching process for trip requests, including driver discovery, ranking, offer distribution, surge pricing, and spatial indexing. This module serves as the core matchmaking engine, coordinating between geospatial queries, pricing calculations, and agent communication to connect riders with appropriate drivers.

## Responsibility Boundaries

- **Owns**: Driver discovery via spatial indexing (H3), composite driver ranking (ETA + rating + acceptance rate), sequential offer cycles with max attempts, surge pricing per zone, thread-safe reservation system to prevent double-matching, trip lifecycle tracking (active/completed/cancelled), puppet driver control flow (manual offer acceptance/rejection)
- **Delegates to**: Trip execution (`trips.trip_executor`), route calculation (`geo.osrm_client`), agent decision-making (`agents.driver_agent`, `agents.rider_agent`), event publishing (`kafka.producer`, `redis_client.publisher`), zone membership (`geo.zones`)
- **Does not handle**: Individual trip state transitions beyond MATCHED (delegated to `TripExecutor`), agent behavior logic (DNA-based decisions in agents), real-time GPS movement simulation (handled by `TripExecutor` and `PuppetDriveController`)

## Key Concepts

**MatchingServer**: Central coordinator (misnamed as "Server" but actually a "Manager"). Maintains thread-safe state with `RLock` for concurrent access from SimPy background thread and FastAPI main thread. Tracks active trips, pending offers, and reserved drivers to prevent race conditions.

**DriverGeospatialIndex**: H3-based spatial index (resolution 9, ~174m edge length) for fast nearest-driver queries. Thread-safe with cell-based organization for efficient radius searches. Automatically rebalances when drivers cross cell boundaries.

**Composite Ranking**: Scores drivers by normalized ETA (inverted, lower is better), rating (1.0-5.0 scale), and acceptance rate (0.0-1.0). Weights are configurable via settings. Drivers offered sequentially in rank order.

**Offer Cycle**: Sequential offer distribution to ranked drivers with configurable max attempts (default 5). For puppet drivers (manual control), cycle pauses and stores remaining candidates in `_pending_offer_candidates` until API action (accept/reject/timeout), then continues automatically. Regular drivers auto-decide based on DNA.

**Driver Reservation**: Atomic check-and-reserve pattern (`_reserved_drivers` set) prevents double-matching during offer window. Reservation released on acceptance (driver tracked via `active_trip`), rejection (back to pool), or error.

**Surge Pricing**: Zone-based multiplier (1.0x-2.5x) calculated every 60 simulated seconds based on pending requests / available drivers ratio. Updates published to Kafka when multiplier changes. Used for trip fare calculation at request time.

**AgentRegistryManager**: Unified facade coordinating updates across multiple registries (agent lookup dict, spatial index, status registry, matching server). Ensures atomic multi-registry updates with thread lock.

**Puppet vs Autonomous**: Puppet drivers (`_is_puppet=True`) require explicit API control (accept/reject offers, drive-to-pickup, start-trip, etc.) and do not run `TripExecutor`. Autonomous drivers auto-decide and execute trips via SimPy processes.

## Non-Obvious Details

The class is named `MatchingServer` but follows the "Manager" pattern (coordinates stateful resources, runs background processes). This is an accepted naming inconsistency documented in `docs/NAMING_CONVENTIONS.md`.

Trip execution is queued (`_pending_trip_executions`) rather than started immediately because matching happens in async context (FastAPI) but `TripExecutor` must start from SimPy thread. The engine calls `start_pending_trip_executions()` each step to safely start queued trips.

Surge calculation uses SimPy process loop, not async/await. The calculator runs autonomously in simulation time, independent of real-time API requests.

Driver registry tracks drivers as "offline" from creation, transitioning to "online" only when explicitly activated. This ensures total driver count is accurate from simulation start.

The geospatial index uses H3's `grid_disk` for k-ring searches, with k calculated dynamically based on search radius: `k = max(1, int(radius_km * 1000 / 174) + 1)`. This ensures complete coverage at resolution 9.

Offer timeout management (`OfferTimeoutManager`) is present but appears unused in current matching flow. Timeout logic is handled via puppet driver API timeout processing instead.

## Related Modules

- **[src/agents](../agents/CONTEXT.md)** — Driver and rider agents that participate in matching; agents submit ride requests and respond to match offers via DNA-based decision logic
- **[src/trips](../trips/CONTEXT.md)** — Trip executor that this module queues for execution after successful match; TripExecutor manages journey from pickup through completion
- **[src/engine](../engine/CONTEXT.md)** — SimPy engine that coordinates thread-safe execution of pending trip processes queued by the matching server
