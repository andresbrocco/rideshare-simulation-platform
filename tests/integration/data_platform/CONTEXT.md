# CONTEXT.md — Data Platform Integration Tests

## Purpose

Validates end-to-end integration of the medallion lakehouse architecture across all services: Kafka ingestion, Spark Structured Streaming, Delta Lake storage, DBT transformations, Airflow orchestration, and BI visualization. Tests data flows from raw events through Bronze/Silver/Gold layers to ensure correctness, reliability, and resilience under realistic failure scenarios.

## Responsibility Boundaries

- **Owns**: Integration test orchestration, Docker lifecycle management, test data generation, cross-service validation, and regression testing of the complete data pipeline
- **Delegates to**: Individual service health checks to service containers, schema definitions to production code in `schemas/`, DBT transformations to `services/dbt/`, data generation logic to fixture modules
- **Does not handle**: Unit testing of individual services, performance benchmarking, production monitoring, or load testing beyond resilience scenarios

## Key Concepts

**Dynamic Docker Profile Management**: Tests use `@pytest.mark.requires_profiles()` markers to declare required Docker Compose profiles (core, data-platform, quality-orchestration, monitoring, bi). The `docker_compose` fixture introspects selected tests to determine which profiles to start, minimizing container overhead and startup time.

**Test Categories**: Tests are organized by concern: foundation (service health), data flows (pipeline correctness), cross-phase (inter-service integration), regression (end-to-end scenarios), and external integrations (API compatibility). Each category validates different architectural boundaries.

**Correlation ID Tracing**: Tests inject unique `correlation_id` values into events to enable precise data lineage tracking through Bronze/Silver/Gold transformations without interference from other concurrent tests or background data.

**Fixture Scope Strategy**: Session-scoped fixtures manage Docker containers and service clients (shared across all tests); function-scoped fixtures handle table cleanup and event generation (isolated per test). This balances test isolation with container startup cost.

**Airflow API Version Detection**: The `AirflowClient` auto-detects API version (v1 for Airflow 2.x with basic auth, v2 for Airflow 3.x with JWT) to maintain compatibility across Airflow versions without configuration changes.

## Non-Obvious Details

Tests wait for Bronze tables to be initialized by the `bronze-init` container, then explicitly create missing tables using DDL from `sql_helpers.py` if streaming jobs haven't written data yet. This ensures tests can run even when no production data exists.

The `clean_*_tables` fixtures truncate Delta tables by deleting S3 objects directly rather than using `DELETE FROM` SQL, as Delta tables preserve history and SQL deletes only mark rows as removed. Direct S3 deletion provides true isolation between test runs.

Checkpoint recovery tests restart streaming containers mid-pipeline to verify exactly-once semantics. The test publishes events before and after restart, then validates all events appear exactly once in Bronze tables, confirming Kafka offset checkpoints restore correctly.

Memory pressure tests publish 1000 events in rapid succession and monitor container memory usage to verify services respect Docker memory limits without OOMKilled failures. This validates backpressure handling and resource constraints under burst load.

Schema Registry compatibility testing uses identical schemas for evolution tests rather than adding optional fields, as JSON Schema compatibility rules in Confluent Schema Registry are strict and adding fields may fail backward compatibility checks.

## Related Modules

- **[infrastructure/docker](../../../infrastructure/docker/CONTEXT.md)** — Uses Docker Compose profile system to orchestrate service dependencies for integration testing
- **[services/spark-streaming](../../../services/spark-streaming/CONTEXT.md)** — Validates Bronze ingestion by verifying Kafka events appear in Delta tables
- **[services/dbt](../../../services/dbt/CONTEXT.md)** — Tests Silver/Gold transformations by querying dimensional models after DBT runs
- **[services/airflow](../../../services/airflow/CONTEXT.md)** — Validates DAG execution and DLQ monitoring via Airflow API
- **[schemas/kafka](../../../schemas/kafka/CONTEXT.md)** — Uses production schemas for test event generation to ensure realistic data contracts
