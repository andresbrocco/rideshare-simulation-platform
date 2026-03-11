# CONTEXT.md — Engine

## Purpose

Orchestrates the SimPy discrete-event simulation environment: manages simulation lifecycle (start/pause/resume/reset), controls simulation time and speed, coordinates thread-safe communication between the FastAPI HTTP layer and the SimPy background thread, and handles agent registration and spawning.

## Responsibility Boundaries

- **Owns**: SimPy environment lifecycle, simulation state machine, real-time ratio (RTR) tracking, agent registration and pending-queue draining, periodic process management (surge updates, spawner loops, checkpointing), thread-safe command passing via `ThreadCoordinator`, and immutable state snapshots for cross-thread reads
- **Delegates to**: `MatchingServer` (match requests, trip lifecycle), `AgentFactory` (agent construction and spawn-queue management), `KafkaProducer` (control events), `RedisPublisher` (real-time state fan-out), `CheckpointManager` (persistence), `SurgePricingCalculator` (zone-level surge), `OSRMClient` (route geometry)
- **Does not handle**: Trip business logic, match scoring, Kafka schema validation, route computation, or WebSocket broadcasting

## Key Concepts

- **SimulationState / two-phase pause**: States are `STOPPED → RUNNING → DRAINING → PAUSED → RUNNING`. Pause is not instant; `_run_drain_process` waits for in-flight trips and repositioning drivers to finish before transitioning to `PAUSED`. If quiescence isn't reached within 7200 simulated seconds, trips are force-cancelled and drivers force-stopped.
- **ThreadCoordinator**: Bridges the FastAPI asyncio main thread and the blocking SimPy background thread. FastAPI sends typed `Command` objects via a `Queue`; the SimPy step loop calls `process_pending_commands()` to drain and execute them, then signals the calling thread via `threading.Event`. All API-to-simulation interactions go through this pattern.
- **Snapshots**: `AgentSnapshot`, `TripSnapshot`, and `SimulationSnapshot` are `frozen=True` dataclasses. They are the only safe way to transfer simulation state to the FastAPI thread without locks; the SimPy thread writes them atomically and the API thread reads them without risk of mutation.
- **Pending-agent queue**: Agents registered mid-simulation (via `AgentFactory` or the command queue) are added to `_pending_agents`. The `step()` method drains this queue via `_start_pending_agents()` before advancing SimPy, ensuring new agents enter the event loop at the correct simulation tick.
- **Spawn queues**: `AgentFactory` maintains four separate `deque`s (driver immediate, driver scheduled, rider immediate, rider scheduled). Four corresponding SimPy spawner processes poll these queues at configurable rates. This decouples the HTTP request to add agents from the actual SimPy process creation.
- **Real-time ratio (RTR)**: Measures simulation speed relative to wall time, accounting for mid-run speed changes. A rolling window of `(wall_perf_counter, env.now, speed_multiplier)` triples is maintained; piecewise normalization per interval makes RTR correct across speed changes.
- **Turbo mode (speed=100)**: Runs SimPy in sub-chunks equal to the matching retry interval instead of one large step, so deferred match retries are dispatched during the step rather than only at its end.
- **TimeManager**: Translates between SimPy's unitless float time (seconds since epoch 0) and real `datetime` objects. All Kafka event timestamps flow through `format_timestamp()`.

## Non-Obvious Details

- `_agent_processes` uses `weakref.WeakSet` so that completed SimPy processes are garbage-collected without explicit removal.
- `active_driver_count` and `active_rider_count` are maintained as incremental counters rather than `len(dict)` to keep reads O(1) even at large agent counts.
- On `reset()`, a fresh `simpy.Environment()` is created and the reference is propagated into `MatchingServer._env` directly. Any component holding a reference to the old `env` will silently stop progressing — components must re-read the engine's `_env` after reset.
- Puppet agents (`_is_puppet = True`) are created by `AgentFactory` with `immediate_online=False`; they enter `offline` state and only transition via explicit API calls. Puppet riders regenerate `frequent_destinations` based on their specified location, not the DNA's randomly generated home.
- `create_puppet_rider` regenerates `frequent_destinations` for both direct-location and zone-based placements; `create_puppet_driver` does not (drivers do not use frequent destinations).
- Zone centroid coordinates from GeoJSON follow `(lon, lat)` convention, but all internal coordinates are `(lat, lon)`. `_get_random_location_in_zone` unpacks centroid as `(centroid_lon, centroid_lat)` — this ordering is easy to confuse.
- S3 checkpoint restore is implemented but SQLite restore is the primary tested path; S3 restore calls `restore_to_engine` without rebuilding agent SimPy processes, so a restored S3 simulation must still call `start()` to launch agent generators.

## Related Modules

- [services/grafana/dashboards/performance](../../../grafana/dashboards/performance/CONTEXT.md) — Shares Pricing & Surge domain (real-time ratio (rtr))
- [services/simulation/tests/engine](../../tests/engine/CONTEXT.md) — Shares SimPy Simulation Engine domain (threadcoordinator)
- [services/simulation/tests/engine](../../tests/engine/CONTEXT.md) — Shares Pricing & Surge domain (real-time ratio (rtr))
