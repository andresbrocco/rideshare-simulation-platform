# CONTEXT.md — Utils (Integration Test Utilities)

## Purpose

Shared infrastructure for the `data_platform` integration test suite. Provides test isolation, credential loading, external service clients, polling helpers, and full-stack state reset — the plumbing that lets integration tests operate against a live Docker environment without interfering with each other.

## Responsibility Boundaries

- **Owns**: Test context ID generation, credential fetching from LocalStack Secrets Manager, HTTP clients for Airflow/Prometheus/Grafana, polling/retry primitives, full-stack state reset (Kafka topics, MinIO buckets, Hive metastore, streaming containers)
- **Delegates to**: boto3 for S3/Secrets Manager access, httpx for HTTP calls, trino for metastore drops, confluent_kafka for topic management, docker compose CLI via subprocess for container restarts
- **Does not handle**: Test fixtures or conftest setup (those live in the parent test package), actual assertion logic, simulation API calls

## Key Concepts

- **TestContext**: A per-test scoped dataclass that mints a unique `test_id` (8-char name prefix + 8-char UUID hex). All entity IDs (`trip_id`, `driver_id`, `rider_id`, `event_id`, `correlation_id`, `marker_id`) are derived from this single root, allowing SQL `LIKE '%{test_id}%'` patterns to precisely scope queries to one test's data even when multiple tests run against the same shared lakehouse.
- **Future timestamps for DBT incremental bypass**: `get_future_ingestion_timestamp()` in `sql_helpers.py` returns timestamps in the year 2099. DBT incremental models filter `_ingested_at > max(_ingested_at)` from Silver; using a far-future timestamp guarantees test-injected Bronze data is always included in the next DBT run regardless of prior Silver state.
- **State reset ordering**: `state_reset.py` enforces a specific teardown order — streaming containers must be stopped before checkpoints are cleared (to release file locks on Delta transaction logs), then buckets are wiped, then metastore entries dropped, then topics deleted and recreated, then containers restarted and given 30 seconds to reinitialize. Deviating from this order causes orphaned metastore entries or locked checkpoint files.

## Non-Obvious Details

- **Credentials mirror `fetch-secrets.py`**: `credentials.py` applies the exact same key-name transforms as `infrastructure/scripts/fetch-secrets.py` (e.g., `FERNET_KEY` → `AIRFLOW__CORE__FERNET_KEY`). These two files must stay in sync manually — there is no shared constant.
- **AirflowClient auto-detects API version**: The client probes `/api/v2/monitor/health` at construction time and switches between Airflow 2.x basic auth and Airflow 3.x JWT (`/auth/token`) accordingly. Tests don't need to know the installed Airflow version.
- **`wait_for_condition` swallows exceptions during polling**: The condition callable's exceptions are caught and ignored — polling continues until timeout. This is intentional for transient connectivity failures but means a consistently-throwing condition will silently time out rather than surface the underlying error.
- **Kafka topic recreation uses 4 partitions, replication factor 1**: These values are hardcoded in `state_reset.py` and must match what the production compose stack expects; mismatches would cause consumer group offset issues.
- **LocalStack endpoint is hardcoded**: `credentials.py` always connects to `http://localhost:4566` with dummy `test`/`test` credentials. This only works when running tests against a local Docker environment — no production credential path exists through this utility.

## Related Modules

- [tests](../../../CONTEXT.md) — Shares Testing Infrastructure and Fixtures domain (testcontext)
- [tests/integration](../../CONTEXT.md) — Reverse dependency — Provides docker_compose, load_credentials, reset_all_state (+7 more)
