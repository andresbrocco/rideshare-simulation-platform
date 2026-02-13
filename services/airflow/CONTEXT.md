# CONTEXT.md — Airflow

## Purpose

Orchestrates the data lakehouse pipeline by scheduling DBT transformations, monitoring dead letter queues for streaming failures, and initializing Bronze layer infrastructure. Serves as the control plane for data quality validation and pipeline health monitoring.

## Responsibility Boundaries

- **Owns**: DAG scheduling, task orchestration, pipeline observability, error threshold monitoring
- **Delegates to**: DBT (Silver/Gold transformations), Great Expectations (data validation), DuckDB with delta/httpfs extensions (DLQ queries), streaming jobs (Kafka→Bronze ingestion via docker-compose)
- **Does not handle**: Direct data transformation, streaming job lifecycle (moved to docker-compose as of 2026-01-18), real-time ingestion

## Key Concepts

- **Medallion Architecture Scheduling**: Separate DAGs for Silver (hourly) and Gold (schedule=None, triggered by Silver DAG) layers with explicit dependency ordering (dimensions → facts → aggregates)
- **DLQ Monitoring**: Queries 8 Delta tables (one per topic, created by 2 consolidated streaming jobs) via DuckDB with delta and httpfs extensions every 15 minutes; branches to alerting when errors exceed threshold (default: 10)
- **Delta Maintenance**: Daily DAG for Delta Lake table optimization (vacuum, compaction)
- **Bronze Initialization**: Manual one-time DAG that creates Hive metastore schema for streaming jobs
- **Great Expectations Integration**: Runs validation checkpoints after DBT transformations; failures logged but don't block pipeline

## Non-Obvious Details

- DLQ monitoring uses DuckDB with delta and httpfs extensions to query Delta tables directly from MinIO, avoiding the need for Spark or Java in the Airflow container
- DLQ queries tolerate missing tables gracefully (expected on first run before streaming jobs create them)
- Silver DAG includes Bronze freshness check (stub implementation)
- Gold DAG generates Great Expectations data docs at end of pipeline for manual review
- LocalExecutor spawns task subprocesses within scheduler; parallelism limited to 8 concurrent tasks

## Related Modules

- **[services/airflow/dags](dags/CONTEXT.md)** — DAG implementations that this service orchestrates; defines the actual transformation and validation workflows
- **[tools/dbt](../../tools/dbt/CONTEXT.md)** — DBT project that Airflow executes for Silver and Gold layer transformations; Airflow schedules and monitors DBT runs
- **[tools/great-expectations](../../tools/great-expectations/CONTEXT.md)** — Data quality validation checkpoints called by Airflow after DBT transformations complete
- **[services/bronze-ingestion](../bronze-ingestion/CONTEXT.md)** — Creates the Bronze Delta tables that Airflow monitors via DLQ checks; provides source data for DBT transformations
- **[infrastructure/scripts](../../infrastructure/scripts/CONTEXT.md)** — Provides check_bronze_tables.py script used in Silver DAG to validate Bronze layer readiness
