# CONTEXT.md — Integration Tests

## Purpose

End-to-end integration tests that verify the full data platform stack running in Docker. Tests exercise the complete event pipeline (Simulation API → Kafka → Stream Processor → Redis → WebSocket) and medallion lakehouse (Bronze → Silver → Gold via Airflow/DBT), using real containerized services rather than mocks.

## Responsibility Boundaries

- **Owns**: Session-scoped Docker lifecycle, credential loading from LocalStack, state reset between test runs, service readiness probes, event generation fixtures
- **Delegates to**: `data_platform/` subdirectory for all actual test modules and utilities
- **Does not handle**: Unit tests (those live in `services/*/tests/`), performance/load testing (in `tests/performance/`), or DBT schema tests

## Key Concepts

**Docker profile-driven test selection**: The `docker_compose` fixture reads `@pytest.mark.requires_profiles()` markers from all selected test items and starts only the needed profiles (`core`, `data-pipeline`, `monitoring`). Tests not requiring Docker set `requires_profiles()` with no arguments.

**Two-phase stream processor readiness**: The `stream_processor_healthy` fixture first polls the `/health` endpoint for `kafka_connected + redis_connected`, then sends a probe message through the full Kafka → Stream Processor → Redis pipeline and waits for it to arrive in Redis pub/sub. This distinguishes "process is alive" from "consumer is actually processing."

**Subscribe-before-publish pattern**: Tests that verify Kafka → Redis forwarding always subscribe to the Redis channel before publishing to Kafka. Publishing first creates a race condition where the stream processor may forward the message before the subscriber is active, causing the message to be silently lost.

**TestContext unique ID isolation**: Each test receives a `TestContext` with a UUID-based `test_id`. All entity IDs (trips, drivers, riders) are derived from this context, enabling SQL filtering by `LIKE '%{test_id}%'` and preventing cross-test contamination without per-test table truncation.

**Session-scoped state reset**: At session start, `reset_all_state` stops streaming containers (to release Delta checkpoint file locks), drops all lakehouse tables via Trino (to clear orphaned Hive metastore entries), clears all MinIO buckets, resets Kafka topics, and restarts streaming containers. Ordering matters: checkpoint locks must be released before bucket clearing, and metastore entries must be dropped before Delta files are removed.

## Non-Obvious Details

- `SKIP_DOCKER_TEARDOWN=1` skips container teardown after tests, useful for faster iteration when containers take a long time to start.
- `clean_bronze_tables`, `clean_silver_tables`, and `clean_gold_tables` fixtures are intentional no-ops. Per-test table truncation was replaced by session-level reset plus `TestContext` ID scoping.
- Airflow uses `/api/v2/monitor/health` (Airflow 3.x) with fallback to `/api/v1/monitor/health` (Airflow 2.x). The health check waits up to 600 seconds because pip installs on first boot are slow.
- `test_data_flows.py`, `test_resilience.py`, `test_cross_phase.py`, and `test_feature_journeys.py` are currently stub files. Their tests were removed when Spark Structured Streaming was replaced by the Python bronze-ingestion service and Trino replaced the Spark Thrift Server for SQL access.
- The Kafka consumer in each test uses `auto.offset.reset: earliest` with a unique `group.id` per test (UUID suffix). This prevents offset conflicts between tests but means each test must drain or filter stale messages from previous runs using unique IDs.
- `test_ci_workflow.py` requires no Docker profiles — it only reads and validates the `.github/workflows/integration-tests.yml` YAML structure.
- Credentials are fetched from LocalStack Secrets Manager (not env files) by `load_credentials`, which sets them as environment variables after `docker_compose` ensures LocalStack is running.

## Related Modules

- [tests/integration/data_platform/fixtures](data_platform/fixtures/CONTEXT.md) — Dependency — Event factory functions that produce synthetic Kafka event payloads for integrat...
- [tests/integration/data_platform/utils](data_platform/utils/CONTEXT.md) — Dependency — Shared test infrastructure for data_platform integration tests: ID scoping, cred...
