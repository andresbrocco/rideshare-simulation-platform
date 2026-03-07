# CONTEXT.md — Tests/Agents

## Purpose

Unit tests for the agent subsystem: DNA models and generators, driver and rider agent state machines, SimPy lifecycle behavior, Kafka event emission, SQLite persistence round-trips, and deferred offer response timing.

## Responsibility Boundaries

- **Owns**: Behavioral correctness of `DriverAgent`, `RiderAgent`, their DNA models, and the agent-facing surface of `MatchingServer` (offer response timing)
- **Delegates to**: `tests/factories.py` (`DNAFactory`) for constructing valid DNA fixtures; `conftest.py` for `mock_kafka_producer`, `dna_factory`, and `temp_sqlite_db` shared fixtures
- **Does not handle**: Integration tests requiring live Kafka or Redis; matching logic correctness (acceptance decision tests live in `tests/matching/test_matching_server.py`)

## Key Concepts

- **DNA-driven testing**: Agent behavior (acceptance rates, shift windows, patience thresholds, surge limits) is parameterized through DNA objects. Tests construct DNA with specific field values to exercise deterministic code paths rather than mocking internal methods.
- **SimPy time simulation**: Lifecycle tests (`test_driver_lifecycle.py`, `test_rider_lifecycle.py`) run `simpy.Environment` forward by wall-clock-equivalent seconds. Initial time is set to place the simulation within the relevant shift window (e.g., `initial_time=5 * 3600` to catch morning shifts quickly). Tests use `@pytest.mark.slow` when they advance many simulated hours.
- **GPS deduplication**: `test_driver_agent.py` and `test_agent_events.py` verify the idle GPS deduplication contract — stationary drivers emit at most one ping per online session, while moving drivers emit on each location change. The `_last_emitted_location` field resets to `None` on `go_offline()`.
- **Deferred offer response**: `test_driver_offer_response.py` tests only SimPy timing of `_deferred_offer_response()`, not the acceptance decision. It patches `random.gauss` to fix the delay and asserts trip state before/after the simulated delay elapses. Response time has a hard floor of 3.0s with no ceiling.
- **Awaiting-pickup state**: `test_awaiting_pickup_state.py` covers the intermediate `awaiting_pickup` rider state (introduced after matching, before pickup arrives). Critically, patience timeout must not fire once a rider reaches `awaiting_pickup` — only while in `requesting`.
- **Persistence round-trips**: `test_agent_persistence.py` uses a temp SQLite database (via `temp_sqlite_db` fixture) to verify `DriverAgent.from_database()` and `RiderAgent.from_database()` restore all mutable fields (status, location, active trip, rating) while preserving frozen DNA immutability.

## Non-Obvious Details

- `test_driver_offer_response.py` disables `_offer_timeout_manager` (`server._offer_timeout_manager = None`) in some tests to prevent the 10-second offer timeout from racing against a longer deferred response delay being tested. Without this, tests with `gauss` return values above ~10s would fail intermittently.
- DNA coordinate validation is geospatially constrained to São Paulo zone boundaries defined in `sample_zones.geojson`. Tests that construct DNA with out-of-zone coordinates (e.g., `(0.0, 0.0)`) expect `ValidationError`. Rider frequent destinations must also be within 20 km of home and at least 0.5 km away (to avoid zero-distance trips).
- `test_rider_agent.py::TestRiderCalculateFare` explicitly tests that the old inline fare constants (`BASE=5, PER_KM=2.5`) are no longer used, verifying the current `FareCalculator` constants (`BASE=4, PER_KM=1.5, MIN=8`) produce a different result for the same input.
- `test_driver_lifecycle.py::test_driver_shift_timing_randomized` seeds `random` differently for each of 3 agents and asserts start times differ, confirming shift jitter is implemented rather than using a fixed offset.
- `test_awaiting_pickup_state.py::TestPuppetAcceptLeavesRiderInAwaitingPickup` tests the puppet driver flow through `MatchingServer.process_puppet_accept()`, verifying `rider.on_driver_en_route()` is called — the only place in the test suite where puppet driver behavior and rider state are tested together.
