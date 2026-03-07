# CONTEXT.md — tests/e2e

## Purpose

Shell-command-based end-to-end test routines that verify simulation checkpoint behavior against a live Docker environment. Unlike unit/integration tests, these routines exercise the full lifecycle of the simulation container — including container restarts, SIGTERM signals, and SQLite persistence — to confirm correctness across four checkpoint triggers: periodic saves, save-on-pause, save-on-SIGTERM, and auto-restore-on-startup.

## Responsibility Boundaries

- **Owns**: E2E test scripts and their documented pass/fail assertion logic for checkpoint integration
- **Delegates to**: Docker Compose for container lifecycle, the simulation API for state control, SQLite for checkpoint verification
- **Does not handle**: Unit-level checkpoint logic (in `src/engine`), test runner automation (these are manual shell routines)

## Key Concepts

- **Checkpoint types**: `graceful` (saved after drain completes with 0 in-flight trips) vs. `crash` (saved under SIGTERM while trips may be active). The DB `simulation_metadata` table stores `checkpoint_type`, `in_flight_trips`, and `current_time`.
- **Drain**: The two-phase pause sequence (RUNNING → DRAINING → PAUSED) where the engine waits for active trips to complete before saving a graceful checkpoint. Drain can complete via `quiescence_achieved` (all trips finished) or `drain_timeout` (2h sim-time elapsed, trips force-cancelled).
- **Speed multiplier**: Tests use `SIM_SPEED_MULTIPLIER=10` or `100` to compress wall-time. At 10x, a 60s checkpoint interval fires in ~6s wall-time. At 100x, the 2-hour drain timeout elapses in ~72s wall-time.
- **Resume from checkpoint**: Controlled by `SIM_RESUME_FROM_CHECKPOINT=true`. If the DB has no checkpoint, the simulation falls back to a fresh start and logs "No checkpoint found, starting fresh simulation".
- **Sequential test dependency**: Tests 1–8 share container state. Test 4 reads checkpoint data written by Test 3. Running tests out of order will produce incorrect results.

## Non-Obvious Details

- Tests are shell routines in a Markdown file (`checkpoint_triggers.md`), not executable test files. They are intended to be run manually by an agent or developer, not by pytest or a CI runner.
- Polling loops all have explicit max iteration counts and `exit 1` on timeout — `|| true` is only used in `grep -c` contexts to avoid false-negative exits when count is zero.
- Test 5 (dirty checkpoint) has a conditional assertion: if SIGTERM arrives between trips, the checkpoint may actually be `graceful` (no in-flight trips at that moment). The test accepts either outcome, asserting only that a checkpoint exists with the expected agent counts.
- The SQLite DB path inside the container is `/app/db/simulation.db`. Checkpoint metadata is queried directly via `sqlite3` inside `docker compose exec` calls.
- Test 6 uses `SIM_SPEED_MULTIPLIER=100` specifically to force the drain timeout within a reasonable wall-time (~72s). The drain trigger is confirmed by log pattern `trigger=quiescence_achieved` or `trigger=drain_timeout`.

## Related Modules

- [infrastructure/docker](../../../../infrastructure/docker/CONTEXT.md) — Dependency — Docker Compose configuration defining the complete local development environment...
- [services/simulation/src/engine](../../src/engine/CONTEXT.md) — Dependency — SimPy simulation environment orchestration, lifecycle state machine, and thread-...
