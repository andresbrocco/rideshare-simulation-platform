# CONTEXT.md — Tools

## Purpose

Houses configuration and code projects that are orchestrated by other services (primarily Airflow) rather than running as standalone Docker containers. These tools define data transformation logic and data quality validation rules for the medallion lakehouse architecture.

## Responsibility Boundaries

- **Owns**: DBT transformation models (Silver/Gold layers), Great Expectations validation suites, data quality contracts
- **Delegates to**: Airflow for scheduling and orchestration, Spark Thrift Server for query execution, MinIO for storage
- **Does not handle**: Data ingestion (Spark Streaming), real-time processing (Stream Processor), or container lifecycle management

## Contents

| Directory | Purpose | CONTEXT.md |
|-----------|---------|------------|
| dbt/ | Medallion architecture transformations (Bronze → Silver → Gold) | [→](dbt/CONTEXT.md) |
| great-expectations/ | Data quality validation for Silver and Gold layers | [→](great-expectations/CONTEXT.md) |

## Key Concepts

**Not Services**: Unlike modules in `services/`, these directories do not have Dockerfiles or run as containers. They are mounted into Airflow containers as volumes and executed within that context.

**Data Quality Pipeline**: DBT transforms data first, then Great Expectations validates the results. Both are orchestrated by Airflow DAGs on schedule.

## Related Modules

- **[services/airflow](../services/airflow/CONTEXT.md)** — Orchestrates both DBT runs and Great Expectations checkpoint executions
- **[services/spark-streaming](../services/spark-streaming/CONTEXT.md)** — Creates Bronze Delta tables that DBT reads from
- **[analytics/superset](../analytics/superset/CONTEXT.md)** — Queries Gold tables produced by DBT transformations
