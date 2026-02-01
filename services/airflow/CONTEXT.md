# CONTEXT.md — Airflow

## Purpose

Orchestrates the data lakehouse pipeline by scheduling DBT transformations, monitoring dead letter queues for streaming failures, and initializing Bronze layer infrastructure. Serves as the control plane for data quality validation and pipeline health monitoring.

## Responsibility Boundaries

- **Owns**: DAG scheduling, task orchestration, pipeline observability, error threshold monitoring
- **Delegates to**: DBT (Silver/Gold transformations), Great Expectations (data validation), Spark Thrift Server (DLQ queries), streaming jobs (Kafka→Bronze ingestion via docker-compose)
- **Does not handle**: Direct data transformation, streaming job lifecycle (moved to docker-compose as of 2026-01-18), real-time ingestion

## Key Concepts

- **Medallion Architecture Scheduling**: Separate DAGs for Silver (hourly) and Gold (daily) layers with explicit dependency ordering (dimensions → facts → aggregates)
- **DLQ Monitoring**: Queries 8 Delta tables (one per topic, created by 2 consolidated streaming jobs) via PyHive every 15 minutes; branches to alerting when errors exceed threshold (default: 10)
- **Bronze Initialization**: Manual one-time DAG that creates Hive metastore schema for streaming jobs
- **Great Expectations Integration**: Runs validation checkpoints after DBT transformations; failures logged but don't block pipeline

## Non-Obvious Details

- Uses PyHive to query Spark Thrift Server instead of running Spark locally (Airflow container lacks Java)
- DLQ queries tolerate missing tables gracefully (expected on first run before streaming jobs create them)
- Silver DAG includes Bronze freshness check (stub implementation)
- Gold DAG generates Great Expectations data docs at end of pipeline for manual review
- LocalExecutor spawns task subprocesses within scheduler; parallelism limited to 8 concurrent tasks

## Related Modules

- **[services/dbt](../dbt/CONTEXT.md)** — Primary orchestration target; Airflow schedules DBT transformations for Silver and Gold layers
- **[quality/great-expectations](../../quality/great-expectations/CONTEXT.md)** — Data quality partner; Airflow triggers Great Expectations checkpoints after DBT runs
- **[services/spark-streaming](../spark-streaming/CONTEXT.md)** — Monitors streaming job health by querying DLQ tables for parsing failures
