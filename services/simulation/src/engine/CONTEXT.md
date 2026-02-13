# CONTEXT.md — Engine

## Purpose

Orchestrates the SimPy discrete-event simulation, managing the lifecycle of the simulation environment, agent processes, periodic processes (surge updates, continuous spawning), and thread-safe communication between the FastAPI main thread and the SimPy background thread.

## Responsibility Boundaries

- **Owns**: Simulation state machine (STOPPED → RUNNING → DRAINING → PAUSED), SimPy environment lifecycle, agent process registration and execution, time management and conversions, two-phase pause with quiescence detection, checkpoint save/restore orchestration
- **Delegates to**: MatchingServer for trip matching logic, AgentFactory for agent creation with DNA, CheckpointManager for SQLite persistence, Kafka/Redis for event publishing
- **Does not handle**: Business logic of matching algorithms, trip execution state transitions, agent behavioral decision-making, route calculations

## Key Concepts

**Two-Phase Pause**: Graceful pause transitions from RUNNING → DRAINING (monitor in-flight trips) → PAUSED (when quiescent or timeout). Prevents corruption by ensuring no trips are mid-execution when checkpointing.

**Thread Coordination**: ThreadCoordinator provides command queue pattern with response events to safely invoke SimPy engine methods from FastAPI thread. Commands block until SimPy thread processes them during step() cycle.

**Time Manager**: Converts between SimPy's unitless time (seconds elapsed) and real datetime objects. Provides helpers for business hours, day number, time-of-day calculations.

**Agent Factory Reference**: Engine stores reference to AgentFactory to enable continuous spawning processes (_driver_spawner_process, _rider_spawner_process) to dynamically create agents at configured rates from spawn queues.

**Session ID**: Each simulation run gets a unique UUID for distributed tracing across events published to Kafka.

## Non-Obvious Details

SimulationEngine.step() calls _start_pending_agents() before advancing time to pick up agents created from the API thread while simulation is running. This enables thread-safe dynamic agent creation without race conditions.

State transition validation enforces valid paths via VALID_STATE_TRANSITIONS dict. Invalid transitions raise ValueError to prevent undefined behavior.

Agent processes are started immediately during continuous spawning (_spawn_single_driver, _spawn_single_rider) but bulk creation via AgentFactory defers process start until next step() cycle. This desynchronizes GPS pings naturally.

Drain process timeout is 7200 simulated seconds (2 hours). If quiescence isn't achieved, all in-flight trips are force-cancelled with system metadata before transitioning to PAUSED.

Snapshots module provides frozen dataclasses for immutable state transfer between threads. These are used by ThreadCoordinator command responses to avoid mutation issues.

## Related Modules

- **[src/agents](../agents/CONTEXT.md)** — Agent processes that the engine manages; engine starts and coordinates agent SimPy processes within its environment
- **[src/matching](../matching/CONTEXT.md)** — Matching server that engine coordinates with for trip execution; engine calls start_pending_trip_executions() each step
- **[src/api/routes](../api/routes/CONTEXT.md)** — FastAPI routes that use ThreadCoordinator to safely invoke engine commands from the web server thread
