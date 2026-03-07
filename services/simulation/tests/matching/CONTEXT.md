# CONTEXT.md — Matching Tests

## Purpose

Unit tests for the matching subsystem: geospatial driver discovery, driver registry state management, surge pricing calculations, offer timeout lifecycle, cross-agent notification dispatch, and thread safety of shared in-memory data structures. Tests run entirely in-process using SimPy environments and mocked external dependencies.

## Responsibility Boundaries

- **Owns**: Behavioral correctness of all classes under `src/matching/`
- **Delegates to**: SimPy `Environment` for time-based lifecycle tests; `h3` library called directly (not mocked) in geospatial tests to validate real spatial behavior
- **Does not handle**: Integration-level broker connectivity, agent lifecycle orchestration, or anything requiring a running Docker environment

## Key Concepts

**Puppet vs. autonomous agents**: The codebase distinguishes "puppet" agents (externally controlled via the API, e.g., by a human or script) from "autonomous" agents (simulated by SimPy processes with DNA-driven decisions). `test_puppet_cross_matching.py` specifically targets the scenario where puppet riders must match with autonomous drivers and vice versa — a cross-type matching path that has distinct code branches.

**Layered diagnostic structure** (`test_puppet_cross_matching.py`): Tests are organized into four labeled layers (spatial discovery, offer cycle, deferred resolution, full request/match flow). This structure was designed to isolate which pipeline layer breaks down in a specific cross-matching regression, not as a general pattern for the other test files.

**Deferred offer resolution**: Autonomous drivers accept or reject offers asynchronously inside a SimPy process (via `random.gauss`-delayed response). Tests that verify deferred resolution must call `server.start_pending_trip_executions()` and advance the SimPy clock (`env.run(until=N)`) after `send_offer_cycle` — otherwise the trip stays at `OFFER_SENT`.

**H3 progressive ring expansion**: `DriverGeospatialIndex` starts with `k=5` rings and expands only when no candidates are found. `test_driver_geospatial_index.py` patches `h3.grid_disk` to count invocations and asserts that a close driver stops expansion at the first call while a distant driver triggers multiple calls.

**Surge pricing tier mapping**: `test_surge_pricing.py` encodes the expected demand/supply ratio → multiplier mapping (ratio ≥ 3 caps at 2.5x, ratio 2 → 1.5x, linear interpolation in between). Tests run SimPy until `t=60` to trigger the 60-second recalculation cycle before asserting `get_surge()`.

**FINDING-002 (Kafka-only surge emission)**: A test class in `test_surge_pricing.py` documents a past architectural issue where `SurgePricingCalculator` published directly to Redis, causing duplicate messages. The tests assert that `redis_publisher.publish_sync` is never called, enforcing that surge events flow exclusively Kafka → API layer → Redis fanout.

## Non-Obvious Details

- Thread safety tests use `STRESS_ITERATIONS = 5` outer loops to catch probabilistic race conditions. Each iteration creates a fresh instance; a failure in any iteration causes the assertion to report the iteration number for debugging.
- `test_notification_dispatch.py` imports from `matching.notification_dispatch` and `trip` without the `src.` prefix, which differs from the absolute import style used in other test files. This is consistent with how pytest is invoked from the `services/simulation/` root with `src/` on the path.
- `test_offer_timeout.py` tests `invalidate_offer` separately from `clear_offer` — both cancel the pending SimPy timeout process, but `invalidate_offer` is called when a trip is re-offered to a different driver (mid-sequence cancellation), while `clear_offer` is called on accepted/rejected outcomes.
- When `redis_publisher=None` is passed to `SurgePricingCalculator`, the calculator must not raise; this is explicitly tested to confirm the parameter is optional post-consolidation.
