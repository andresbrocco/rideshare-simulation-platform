# CONTEXT.md — Data Platform Integration Tests

## Purpose

Validates end-to-end integration of the data platform across all services: the core event flow (Simulation API → Kafka → Stream Processor → Redis → WebSocket), Spark Structured Streaming for Bronze ingestion, Delta Lake storage, and DBT transformations. Tests focus on data correctness, reliability, and resilience under realistic failure scenarios.

## Responsibility Boundaries

- **Owns**: Integration test orchestration, Docker lifecycle management, test data generation, cross-service validation, core pipeline testing, and resilience testing of the complete data platform
- **Delegates to**: Individual service health checks to service containers, schema definitions to production code in `schemas/`, DBT transformations to `tools/dbt/`, data generation logic to fixture modules
- **Does not handle**: Unit testing of individual services, performance benchmarking, production monitoring, load testing, or vendor service validation (Airflow, Superset, Great Expectations)

## Key Concepts

**Dynamic Docker Profile Management**: Tests use `@pytest.mark.requires_profiles()` markers to declare required Docker Compose profiles (core, data-pipeline). The `docker_compose` fixture introspects selected tests to determine which profiles to start, minimizing container overhead and startup time.

**Test Categories**: Tests are organized into focused categories:
- **Core Pipeline** (`core_pipeline`): Tests the real-time event flow from Simulation API through Kafka, Stream Processor, Redis pub/sub, to WebSocket clients
- **Resilience** (`resilience`): Tests data consistency under partial failures, trip state machine integrity, and pipeline smoke tests
- **Feature Journey** (`feature_journey`): Tests Bronze ingestion and DBT Silver transformations
- **Data Flow** (`data_flow`): Tests data lineage and deduplication
- **Cross-Phase** (`cross_phase`): Tests integration between MinIO + Streaming and Bronze + DBT

**Correlation ID Tracing**: Tests inject unique `correlation_id` or `trip_id` values into events to enable precise data lineage tracking through Bronze/Silver transformations without interference from other concurrent tests.

**Fixture Scope Strategy**: Session-scoped fixtures manage Docker containers and service clients (shared across all tests); function-scoped fixtures handle table cleanup, Kafka consumers, and Redis publishers (isolated per test). This balances test isolation with container startup cost.

## Non-Obvious Details

Tests wait for Bronze tables to be initialized by the `bronze-init` container, then explicitly create missing tables using DDL from `sql_helpers.py` if streaming jobs haven't written data yet. This ensures tests can run even when no production data exists.

The `clean_*_tables` fixtures truncate Delta tables by deleting S3 objects directly rather than using `DELETE FROM` SQL, as Delta tables preserve history and SQL deletes only mark rows as removed. Direct S3 deletion provides true isolation between test runs.

WebSocket tests use `websockets.sync.client` with API key authentication via the `Sec-WebSocket-Protocol: apikey.<key>` subprotocol header, matching the production authentication mechanism.

Schema Registry enforcement tests verify the pipeline handles malformed events gracefully—invalid events don't corrupt the system, and valid events published after invalid ones still flow correctly.
