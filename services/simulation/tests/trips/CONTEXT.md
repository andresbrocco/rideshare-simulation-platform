# CONTEXT.md — tests/trips

## Purpose

Unit tests for `TripExecutor`, the SimPy-based component that drives a single trip through its full lifecycle (DRIVER_ASSIGNED → EN_ROUTE_PICKUP → AT_PICKUP → IN_TRANSIT → COMPLETED or CANCELLED). Tests are split into four focused modules: core event emission guarantees, GPS proximity arrival detection, post-trip rating submission, and OSRM error recovery.

## Responsibility Boundaries

- **Owns**: Behavioral specification for `TripExecutor` including event routing, GPS interval correctness, cancellation logic, rating emission, and OSRM retry semantics
- **Delegates to**: `conftest.py` (shared `dna_factory`, `mock_kafka_producer` fixtures), `tests.factories.DNAFactory` for agent DNA construction
- **Does not handle**: Matching server logic, agent GPS loop behavior (that is the agent's responsibility, not the executor's), or integration-level Kafka/Redis concerns

## Key Concepts

- **FINDING-002**: A documented architectural finding that `TripExecutor` must emit trip events to Kafka only — Redis receives them via the API layer's filtered fanout. Tests in `test_trip_executor.py` serve as regression guards for this invariant.
- **GPS_PING_INTERVAL_MOVING**: A configured constant (not hardcoded `1`) that governs how often the drive loop advances. `TestTripExecutorGPSInterval` exists specifically because a hardcoded interval of `1` caused GPS ping duplication; the test uses source inspection (`inspect.getsource`) to enforce the constant is referenced.
- **Precomputed headings**: `_simulate_drive()` must call `precompute_headings()` once per route rather than instantiating `GPSSimulator` per tick. `TestTripExecutorPrecomputedHeadings` enforces this with source inspection.
- **DNA-based cancellation**: Driver cancellation probability is modulated by `cancellation_tendency` DNA trait and scaled by ETA (clamped to `[0.5, 2.0]` via `max(0.5, min(2.0, eta_minutes / 10.0))`). Tests use `@patch("src.trips.trip_executor.random.random")` with values `0.0` and `1.0` to exercise the threshold deterministically.
- **PATTERN-006 error recovery**: `NoRouteFoundError` is a permanent failure (no retry); `OSRMTimeoutError` and `OSRMServiceError` are transient (exponential backoff with configurable `osrm_max_retries`, `osrm_retry_base_delay`, `osrm_retry_multiplier`). The cleanup handler was intentionally removed — unrecoverable errors propagate to the caller (`MatchingServer`).
- **Proximity arrival detection**: Arrival is detected by Haversine distance falling below `arrival_proximity_threshold_m` (default 50m, range 10–500m), not by OSRM route completion. `arrival_timeout_multiplier` sets a fallback ceiling.

## Non-Obvious Details

- Tests use `random.seed()` before runs involving probabilistic rating submission because rating events are emitted with a DNA-influenced probability. Tests that check for zero ratings (cancelled trips) or verify content fields are deterministic, but tests checking positive emission counts acknowledge the probabilistic nature and avoid asserting exact counts.
- Source inspection via `inspect.getsource()` is used in two test classes to verify that implementation code references specific symbols (`GPS_PING_INTERVAL_MOVING`, `precompute_headings`, `route_headings`) and does not contain forbidden patterns (`GPSSimulator(noise_meters=0)`, `gps_interval = 1`). This is a non-standard but intentional technique to guard against regressions that preserve behavior while reintroducing the wrong mechanism.
- `TripExecutor` accepts `redis_publisher=None` and must function correctly without it. Tests verify that passing a mock `redis_publisher` results in zero calls to that mock — the parameter exists for backward compatibility but is intentionally unused.
- The exponential backoff test (`test_exponential_backoff_timing`) verifies delays using SimPy's simulated clock (`simpy_env.now`), not wall time. Delays of 0.5s, 1.0s, and 2.0s are asserted with `< 0.01` tolerance against simulated timestamps.
