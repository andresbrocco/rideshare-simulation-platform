# CONTEXT.md — tests/engine

## Purpose

Unit tests for the simulation engine subsystem, covering the orchestrator lifecycle, thread-safe command bridging between FastAPI and SimPy, two-phase pause protocol, speed control and real-time ratio measurement, checkpoint persistence triggers, and immutable snapshot dataclasses used for thread-safe state transfer.

## Responsibility Boundaries

- **Owns**: All tests for `src/engine/` — `SimulationEngine`, `ThreadCoordinator`, `TimeManager`, `AgentFactory`, and the `snapshots` module
- **Delegates to**: `conftest.py` for shared `fast_engine` and `fast_running_engine` fixtures used across multiple test files
- **Does not handle**: Agent behavior tests (drivers, riders), Kafka or Redis integration tests, API route tests

## Key Concepts

- **`fast_engine` fixture**: Uses `TEST_SPEED_MULTIPLIER = 60` to prevent real wall-clock waits in `step()` calls. Tests that call `step()` rely on this fixture rather than a default-speed engine.
- **Two-phase pause**: `pause()` transitions to `DRAINING` first (rejecting new match requests), waits for in-flight trips and repositioning drivers (`driving_closer_to_home`) to quiesce, then transitions to `PAUSED`. A 7200-second drain timeout force-stops any remaining repositioning drivers.
- **Real-time ratio (RTR)**: Computed via a sliding sample window. Each sample stores `(wall_time, sim_time, speed_multiplier)`. At speed regime boundaries, `step()` records a duplicate sample at the new speed with the same sim-time, which the algorithm skips (zero wall delta). This allows piecewise normalization across speed changes without resetting the window.
- **ThreadCoordinator**: FIFO command queue bridging FastAPI threads (`send_command` blocks on an `Event`) with the SimPy loop (`process_pending_commands` called each `step()`). Error propagation re-raises handler exceptions on the caller side.
- **Checkpoint triggers**: Four trigger sites are tested — periodic process (configurable interval, survives exceptions), on-pause (`_transition_to_paused`), on-SIGTERM (shutdown handler closure in `main.py`, reconstructed in tests), and auto-restore on startup (`resume_from_checkpoint` setting).

## Non-Obvious Details

- `test_simulation_engine.py` imports from `engine` (bare module, no `src.` prefix) while most other test files import from `src.engine`. This reflects the test's position within the `services/simulation` package where `PYTHONPATH` includes both root paths.
- All engine tests are marked `@pytest.mark.slow` in addition to `@pytest.mark.unit` because even with the speed multiplier, SimPy process tests take longer than pure unit tests.
- `test_resume_restarts_processes` asserts `resumed_process_count == initial_process_count * 2` — resume re-registers all agent processes into the WeakSet, doubling the count before dead references are collected.
- The shutdown handler test (`TestCheckpointOnShutdown`) cannot import the real closure from `main.py` (it is defined inline during startup), so it reconstructs the same logic from mocks. The test verifies call order: `runner_stop → checkpoint → engine_stop → flush`.
- Spawn queue deque tests verify O(1) `popleft` semantics: each deque entry is a batch count (integer), and `dequeue_*` methods decrement that count internally, returning `True` per agent until exhausted. Zero-count entries are discarded.

## Related Modules

- [schemas/api](../../../../schemas/api/CONTEXT.md) — Shares SimPy Simulation Engine domain (two-phase pause)
- [schemas/api](../../../../schemas/api/CONTEXT.md) — Shares Unified Process & Time Management domain (two-phase pause)
- [services/grafana/dashboards/performance](../../../grafana/dashboards/performance/CONTEXT.md) — Shares Pricing & Surge domain (real-time ratio (rtr))
- [services/simulation/src/engine](../../src/engine/CONTEXT.md) — Shares SimPy Simulation Engine domain (threadcoordinator)
- [services/simulation/src/engine](../../src/engine/CONTEXT.md) — Shares Pricing & Surge domain (real-time ratio (rtr))
