# CONTEXT.md — Engine Tests

## Purpose

Tests the SimulationEngine orchestrator and its thread-safe coordination mechanisms. Validates complex patterns for managing discrete-event simulation (SimPy) from a concurrent web API (FastAPI), including state machine transitions, speed control with wall-clock pacing, and cross-thread state snapshots.

## Responsibility Boundaries

- **Owns**: Testing simulation lifecycle (start/stop/pause/resume), speed multiplier behavior, two-phase pause protocol, thread-safe command queue, immutable snapshot generation, agent registration and process spawning
- **Delegates to**: `src/engine` for actual implementation, `conftest.py` for shared test fixtures (mock_sqlite_db, fast_engine)
- **Does not handle**: Agent behavior tests (covered by `tests/agents/`), trip state machine tests (covered by `tests/trips/`), matching algorithm tests (covered by `tests/matching/`)

## Key Concepts

### Two-Phase Pause Protocol
The engine transitions through DRAINING state before reaching PAUSED to ensure in-flight trips complete gracefully. Tests validate:
- RUNNING → DRAINING → PAUSED state sequence
- Rejection of new trip requests during DRAINING
- Quiescence detection (waiting for all trips to reach terminal state)
- Force-cancellation of trips after drain timeout
- Correct trigger metadata (quiescence_achieved vs drain_timeout)

### ThreadCoordinator Command Queue
Thread-safe bridge between FastAPI (async, multi-threaded) and SimPy (synchronous, single-threaded). Tests validate:
- Command submission from any thread with blocking wait
- FIFO processing order
- Handler registration and invocation
- Error propagation from handler back to caller
- Timeout and shutdown behavior
- Concurrent command processing without race conditions

### Speed Multiplier with Wall-Clock Pacing
Controls simulation speed relative to real time (1x = real-time, 100x = no pacing). Tests validate:
- Speed changes emit control events
- Invalid speeds (≤0) are rejected
- Speed multiplier property reflects current value

Note: Wall-clock pacing tests removed due to excessive runtime (10+ seconds per test). Speed logic validated via unit tests only.

### Immutable Snapshots
Frozen dataclasses (AgentSnapshot, TripSnapshot, SimulationSnapshot) for thread-safe state transfer. Tests validate:
- Immutability (AttributeError on field modification)
- Serialization to dict
- Tuple usage for collections (drivers, riders, active_trips)
- Datetime handling in serialized output

## Non-Obvious Details

### TEST_SPEED_MULTIPLIER Constant
`conftest.py` defines `TEST_SPEED_MULTIPLIER = 60` to accelerate tests. At 60x, a `step(60)` call completes in ~1 second instead of 60 seconds. Tests marked `@pytest.mark.slow` still run quickly due to this optimization.

### fast_engine Fixture Pattern
Many tests use `fast_engine` fixture (60x speed) or `fast_running_engine` (60x speed + RUNNING state) instead of creating engines at real-time speed. This pattern keeps test suite execution time manageable.

### Mock SQLite Pattern
`create_mock_sqlite_db()` returns a context manager factory that yields a mock session. This matches the production interface `with sqlite_db() as session:` without requiring actual database operations.

### SimPy Process Tracking
Tests verify that `engine.start()` calls `agent.run()` for all registered agents by checking `agent.run.called` on mock agents. The `_process_started` attribute is used internally to track which agents have been started.

### FIFO Verification Strategy
ThreadCoordinator FIFO tests bypass `send_command()` and directly queue Command objects to avoid timing-dependent test flakiness. The test then processes all commands in one batch and verifies order.

## Related Modules

- **[src/engine](../../src/engine/CONTEXT.md)** — SimulationEngine implementation under test; tests validate lifecycle, threading, and coordination patterns
- **[tests](../CONTEXT.md)** — Parent test infrastructure providing shared fixtures and DNAFactory for engine tests
- **[src/agents](../../src/agents/CONTEXT.md)** — Agent processes that engine manages; tests mock agent.run() to verify process spawning
