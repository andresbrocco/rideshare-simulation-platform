# CONTEXT.md — Data Platform Integration Tests

## Purpose

End-to-end integration tests that exercise the full data platform stack against live Docker containers. Tests verify event flow from the Simulation API through Kafka, Stream Processor, Redis pub/sub, WebSocket delivery, and the medallion lakehouse (Bronze → Silver → Gold via Airflow/DBT/Trino). Also includes CI/CD workflow validation and infrastructure health checks.

## Responsibility Boundaries

- **Owns**: Live-service integration verification, Docker lifecycle management, session-scoped state reset, credential loading from LocalStack, service readiness probing
- **Delegates to**: `utils/state_reset.py` for MinIO/Kafka/Hive teardown logic, `utils/credentials.py` for LocalStack secret fetching, `fixtures/` modules for synthetic event generation, `utils/api_clients.py` for Airflow/Grafana/Prometheus HTTP clients
- **Does not handle**: Unit testing, performance load testing (see `tests/performance/`), DBT-level testing (see `tools/dbt/tests/`)

## Key Concepts

- **`requires_profiles` marker**: Tests declare which Docker Compose profiles they need (`core`, `data-pipeline`, `monitoring`). The `docker_compose` session fixture dynamically starts only the profiles required by the tests that will actually run after filtering — not all profiles unconditionally.
- **Session-scoped state reset**: `reset_all_state` runs once per session and clears all persistent state in a specific order: (1) stop streaming containers to release checkpoint file locks, (2) drop Hive metastore tables via Trino to prevent orphaned entries after MinIO is cleared, (3) clear MinIO buckets, (4) delete and recreate Kafka topics, (5) restart streaming containers. Violating this order causes file lock errors or orphaned metastore entries pointing to non-existent Delta files.
- **TestContext**: Each test receives a `TestContext` with a unique `test_id` (test name prefix + UUID fragment) used to generate namespaced entity IDs (trip, driver, rider, event). This enables tests to filter Trino/Kafka queries for only their own data without per-test table cleanup.
- **Probe message pattern**: The `stream_processor_healthy` fixture uses a subscribe-before-publish pattern when verifying the Kafka → Stream Processor → Redis pipeline. The Redis subscriber is registered before the Kafka message is produced to avoid the race condition where the stream processor forwards the message before the subscriber is active.
- **Two-phase stream processor readiness**: `stream_processor_healthy` first polls the `/health` endpoint until `kafka_connected` and `redis_connected` are both `true`, then sends an actual probe message through the full pipeline to confirm the consumer has rebalanced and is processing. Health endpoint alone is insufficient because topic deletion/recreation during `reset_all_state` disrupts consumer group assignments.

## Non-Obvious Details

- **Fixture dependency chain**: `docker_compose` → `load_credentials` → `reset_all_state` → `wait_for_services` → service-specific fixtures. `load_credentials` is `autouse=True` and session-scoped, so it runs automatically once Docker is up and populates env vars (`API_KEY`, `MINIO_ROOT_USER`, `KAFKA_SASL_USERNAME`, etc.) for all downstream fixtures.
- **Credentials come from LocalStack, not `.env`**: `fetch_all_credentials()` fetches the four `rideshare/*` secrets from LocalStack Secrets Manager at runtime and applies the same key transforms as `infrastructure/scripts/fetch-secrets.py`. Tests must not expect credentials pre-set in the environment.
- **Several test files are now stubs**: `test_data_flows.py`, `test_cross_phase.py`, `test_resilience.py`, and `test_feature_journeys.py` contain only module-level markers. Their original tests were removed when Spark Thrift Server was replaced by Trino, and new Trino-based equivalents have not yet been written.
- **`SKIP_DOCKER_TEARDOWN=1`**: Setting this env var skips container teardown after the session, useful for faster iteration when containers are slow to start.
- **Kafka consumer uses unique group IDs per test**: The `kafka_consumer` fixture (function-scoped) generates a fresh consumer group ID each invocation (`integration-test-consumer-<uuid>`) to avoid offset conflicts between tests.
- **Airflow version compatibility**: The `wait_for_services` fixture tries Airflow v2 (`/api/v2/monitor/health`) before falling back to v1 (`/api/v1/monitor/health`).
- **Puppet agents for controlled trip generation**: `test_simulation_api_kafka_publishing` uses the simulation's puppet agent API (`/agents/puppet/drivers`, `/agents/puppet/riders`, `/agents/puppet/riders/{id}/request-trip`) to trigger trip events deterministically, bypassing the DNA-based probabilistic scheduling that autonomous agents use.

## Related Modules

- [tests/integration/data_platform/utils](utils/CONTEXT.md) — Shares Testing Patterns & Fixtures domain (testcontext)
