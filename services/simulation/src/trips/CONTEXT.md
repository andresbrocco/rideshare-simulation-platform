# CONTEXT.md — Trips

## Purpose

Orchestrates the end-to-end lifecycle of a single rideshare trip within the SimPy simulation, from driver dispatch through fare settlement. It owns the SimPy generator coroutines that advance trip state, move agents through space, and emit Kafka events at each phase boundary.

## Responsibility Boundaries

- **Owns**: Trip phase sequencing (pickup drive → rider wait → transit drive → completion), GPS interpolation along OSRM routes during trip execution, cancellation decision logic (pre-pickup, mid-trip, probabilistic), payment event emission, and per-trip statistics recording
- **Delegates to**: `geo.osrm_client` for route geometry, `geo.gps_simulation` for heading precomputation, `geo.distance` for proximity detection, `events.factory` for event construction, `kafka.producer` for publishing, agent methods (`start_pickup`, `complete_trip`, etc.) for agent-side state changes
- **Does not handle**: Driver–rider matching (owned by `matching`), GPS ping background loops (owned by agents), trip domain model and state machine (owned by `trip` module), H3 spatial indexing

## Key Concepts

- **Two drive implementations**: `TripExecutor._simulate_drive` is the full trip drive that tracks route progress indexes, mirrors rider location, checks both rider and driver mid-trip cancellations, and propagates state to agents. `simulate_drive_along_route` in `drive_simulation.py` is a stripped-down variant with no trip state — used exclusively for repositioning drives (home-return) where none of those side effects are needed.
- **Proximity-based arrival detection**: Both drive methods support early exit when the interpolated position comes within `arrival_proximity_threshold_m` meters of the destination, replacing purely time-based arrival. This avoids overshooting the target when OSRM durations are imprecise.
- **DNA-scaled pre-pickup cancellation**: Cancel probability = `driver.dna.cancellation_tendency × distance_scaling`, where `distance_scaling` grows with ETA (capped 0.5–2.0×). Longer pickups are more likely to be cancelled by the driver.
- **Probabilistic mid-trip cancellations**: Both rider and driver mid-trip cancellations are decided before the drive loop starts; the cancellation interval is sampled from the second half of the route so partial trips always have meaningful distance covered.
- **Payment is a leaf event**: `_emit_payment_event` creates a `PaymentEvent` with `update_causation=False`, meaning it does not advance the distributed tracing causation chain — it is a terminal event branching off the trip's correlation chain.
- **Platform fee hardcoded at 25%**: Driver receives 75% of fare; platform retains 25%. This is not configurable via settings.

## Non-Obvious Details

- `_simulate_drive` advances both `route_progress_index` (for `IN_TRANSIT`) and `pickup_route_progress_index` (for `EN_ROUTE_PICKUP`) on the `Trip` object, and propagates these to agents via `update_route_progress`. This dual-index design feeds the frontend progress bar for both the pickup and trip legs independently.
- The `_wait_for_rider` step explicitly sets `pickup_route_progress_index` to the last point of the pickup route, ensuring 100% pickup progress is visible even when arrival is detected early via proximity rather than completing all loop intervals.
- `execute()` checks `trip.state == TripState.CANCELLED` after each phase to support cancellations that happen inside sub-generators; this is needed because SimPy generators cannot propagate cancellations via exceptions across `yield from` boundaries.
- The OSRM retry loop uses `yield self._env.timeout(delay)`, meaning retry delays consume simulated time, not wall-clock time.

## Related Modules

- [services/simulation/src/agents](../agents/CONTEXT.md) — Reverse dependency — Provides DriverAgent, RiderAgent, DriverDNA (+8 more)
