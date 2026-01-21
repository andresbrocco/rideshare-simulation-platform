# CONTEXT.md — Puppet

## Purpose

Controls API-driven "puppet" agents that operate outside the SimPy simulation loop. Puppet agents are manually controlled through REST API endpoints for testing and demonstration purposes, providing deterministic behavior where autonomous agents would be non-deterministic.

## Responsibility Boundaries

- **Owns**: Background thread movement of puppet drivers along OSRM routes with GPS emission
- **Delegates to**: GPS simulation for heading calculation, Kafka/Redis for event publishing, Trip object for route progress tracking
- **Does not handle**: Trip state transitions (handled by MatchingServer), route planning (uses pre-calculated OSRM routes), autonomous agent behavior

## Key Concepts

**Puppet Agents**: Special agents marked with `_is_puppet=True` attribute that bypass SimPy's event loop. All actions (going online, accepting offers, driving) are triggered via API calls rather than agent DNA-driven behavior.

**Drive Controller**: Manages a single drive segment (pickup or destination) in a background thread, emitting GPS pings at regular intervals and updating driver location along the route geometry. Operates independently of SimPy simulation time.

**Speed Multiplier**: Adjusts real-world time to match simulation speed (e.g., 10x multiplier means a 60-second route completes in 6 real seconds).

## Non-Obvious Details

The drive controller runs in a daemon thread separate from both the SimPy simulation thread and FastAPI main thread. This allows puppet drives to progress while the simulation is paused or even stopped.

Completion callbacks are executed in the drive thread, not the simulation thread, requiring thread-safe coordination when updating shared state.

Route progress is tracked on the Trip object via `pickup_route_progress_index` and `route_progress_index` fields, allowing the frontend to animate movement along the path.
