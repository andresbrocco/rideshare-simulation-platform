# CONTEXT.md — Tests

## Purpose

Cross-service test suite covering two distinct test categories: integration tests that validate the data platform pipeline end-to-end (Kafka → Bronze ingestion → Delta Lake), and performance tests that benchmark container resource consumption under configurable simulation load scenarios.

## Responsibility Boundaries

- **Owns**: Integration test fixtures and event factories for data platform validation; performance scenario harness with Docker lifecycle management, Prometheus metric collection, and OOM detection
- **Delegates to**: Service-level unit tests in `services/simulation/tests/`, `services/airflow/tests/`, and DBT schema tests in `tools/dbt/tests/`
- **Does not handle**: Unit or component tests for individual services — those live alongside their source code

## Key Concepts

**TestContext** (`tests/integration/data_platform/utils/test_context.py`): Generates structured, predictable identifiers (trip, driver, rider, event, correlation IDs) scoped to a single test run using a UUID suffix. This enables parallel test execution without ID collisions and allows SQL `WHERE id LIKE '%{test_id}%'` filtering to isolate each test's data in shared Delta tables.

**Event fixture factories** (`tests/integration/data_platform/fixtures/`): Synthetic event generators for GPS pings, trip lifecycle sequences, driver status changes, and rider profile events. Factories emit dicts matching the Kafka schema registry contracts so tests inject realistic data directly into Kafka topics without running the full simulation service.

**BaseScenario** (`tests/performance/scenarios/base.py`): Abstract base class for performance scenarios. Each scenario follows a three-phase protocol — setup (clean Docker restart via `down -v` + `up -d`), execute (generator-based progress loop), teardown. Scenarios can declare `requires_clean_restart = False` to reuse a previous scenario's container state, saving startup time in sequential test suites.

**OOMDetector** (`tests/performance/collectors/oom_detector.py`): Detects container out-of-memory kills by polling `docker inspect` for `OOMKilled` flag and `RestartCount` changes against a captured baseline. A companion `MemoryWarningTracker` emits early warnings at >95% memory usage. When OOM is detected mid-scenario, the scenario is marked aborted and the run continues to the next scenario rather than failing the entire suite.

**generate_test_events.py** (`tests/integration/data_platform/producers/`): Standalone CLI script that publishes synthetic events directly to Kafka topics, usable for manual integration testing and stress seeding outside of pytest.

## Non-Obvious Details

- Integration tests require the full data platform Docker stack running (`data-pipeline` profile). There is no mocking of Kafka, MinIO, or the Bronze ingestion service — tests assert on actual Delta table record counts via polling with exponential backoff.
- The `wait_for_condition` helper in `wait_helpers.py` silently swallows exceptions during polling (to tolerate transient connectivity failures) and uses exponential backoff capped at 10 seconds. A test that never converges will surface only after the full timeout, not immediately on first exception.
- Performance test results are written to timestamped subdirectories under `tests/performance/results/` and are committed to the repo. These are historical benchmark snapshots, not test artifacts to be cleaned up.
- The `run_integration_tests.sh` script in `tests/integration/data_platform/` contains a stale path reference (`./venv/bin/pytest data-pipeline/tests/test_foundation_integration.py`). The actual integration tests are under `tests/integration/`, not `data-pipeline/tests/`.
- Global CPU in performance samples is summed across all monitored containers, which can exceed 100% on multi-core hosts. The `available_cores` field in each sample provides the denominator for normalizing CPU utilization.

## Related Modules

- [tests/integration/data_platform/utils](integration/data_platform/utils/CONTEXT.md) — Shares Testing Infrastructure and Fixtures domain (testcontext)
- [tests/performance/scenarios](performance/scenarios/CONTEXT.md) — Shares Performance and Load Testing domain (basescenario)
