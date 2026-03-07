# CONTEXT.md — Puppet

## Purpose

Provides API-controlled driver movement outside the SimPy discrete-event loop. "Puppet" agents are driven by direct API calls (rather than autonomous SimPy processes), and their movement along OSRM routes is executed in real-time background threads, not in simulated time.

## Responsibility Boundaries

- **Owns**: Background-threaded route traversal for puppet drivers; GPS ping emission during puppet drives; rider position mirroring during the destination leg
- **Delegates to**: `geo.gps_simulation.GPSSimulator` for heading calculation; `kafka.producer` and `redis_client.publisher` for event emission; `SimulationEngine` for simulation-time timestamp formatting
- **Does not handle**: SimPy process scheduling, trip lifecycle state transitions, or agent state machines — callers manage those via completion callbacks

## Key Concepts

**Puppet vs. autonomous agents**: Standard simulation agents are SimPy generator processes that advance with simulated time. Puppet agents are created and controlled via REST API; their drives run in OS threads using `time.sleep`, so wall-clock time governs movement speed rather than the SimPy clock.

**Speed multiplier**: Scales how quickly real time elapses relative to the route's OSRM duration. A multiplier of `2.0` makes a 60-second route complete in 30 real seconds. Both the total duration and the GPS interval are divided by the multiplier, keeping the number of emitted pings constant regardless of speed.

**Pickup vs. destination leg**: `is_pickup_drive=True` means the driver is traveling to pick up the rider; the rider stays at the pickup location. `is_pickup_drive=False` means the rider is in the vehicle and their position is mirrored to match the driver's position at every GPS interval.

**Completion callbacks**: Callers register callables via `on_completion()`. These fire synchronously in the drive thread after the final GPS ping, so callbacks must be thread-safe.

## Non-Obvious Details

- GPS noise is set to `0` for puppet drives (`GPSSimulator(noise_meters=0)`), producing exact route geometry coordinates with no jitter.
- Speed is emitted as a random uniform value between 20–60 (approximate city speed), not derived from the route geometry.
- The minimum allowed speed multiplier is clamped at `0.125` to prevent extremely long-running background threads.
- Timestamps in GPS pings use the simulation engine's time manager when available; they fall back to wall-clock UTC when no engine is present (e.g., in isolated testing).
- The Redis publisher is intentionally absent from the `_emit_gps_ping` method — only Kafka receives GPS pings from this controller.

## Related Modules

- [services/grafana/dashboards/performance](../../../grafana/dashboards/performance/CONTEXT.md) — Shares SimPy Discrete-Event Simulation domain (speed multiplier)
- [services/grafana/dashboards/performance](../../../grafana/dashboards/performance/CONTEXT.md) — Shares Time and Simulation Speed domain (speed multiplier)
