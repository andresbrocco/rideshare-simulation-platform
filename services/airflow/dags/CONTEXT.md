# CONTEXT.md — Airflow DAGs

## Purpose

Orchestrates the data pipeline transformations and quality checks for the rideshare medallion lakehouse architecture. Manages the Bronze → Silver → Gold transformation lifecycle with DBT, monitors data quality with Great Expectations, and tracks errors in dead-letter queues (DLQ).

## Responsibility Boundaries

- **Owns**: Scheduling and execution of DBT transformations, Great Expectations validations, and DLQ monitoring
- **Delegates to**: DBT for SQL transformations (`/opt/dbt`), Great Expectations for data validation (`/opt/great-expectations`), DuckDB with delta/httpfs extensions for DLQ queries
- **Does not handle**: Direct data processing (done by Spark Structured Streaming), schema evolution, or Kafka topic management

## Key Concepts

**Layer Transformation Schedules**
- Silver layer runs hourly with Bronze freshness checks
- Gold layer has `schedule=None`, triggered by Silver DAG conditionally, with dependency ordering: dimensions → facts → aggregates

**DLQ Monitoring**
- Queries 8 DLQ Delta tables every 15 minutes via DuckDB with delta and httpfs extensions
- Uses branching logic: threshold exceeded → alert, otherwise → no-op
- Threshold: 10 errors across all tables in 15-minute window

## Non-Obvious Details

**Silver DAG Task Flow**
1. Check Bronze freshness (placeholder - always passes)
2. Run DBT models tagged `silver`
3. Run DBT tests on Silver models
4. Run Great Expectations `silver_validation` checkpoint (continues on failure with warning)
5. Export Silver data to S3

**Gold DAG Task Flow**
1. Seed reference data (`dbt seed`)
2. Build dimension tables (`tag:dimensions`)
3. Build fact tables (`tag:facts`) - depends on dimensions
4. Build aggregates (`tag:aggregates`) - depends on facts
5. Run all Gold tests (`tag:gold`)
6. Run Great Expectations `gold_validation` checkpoint
7. Export Gold data to S3

**DLQ Monitoring Implementation**
- Uses DuckDB with delta and httpfs extensions to query Delta tables directly from MinIO
- Gracefully handles missing tables (expected on first run)
- Uses XCom to pass error counts between tasks for branching logic

**Error Handling**
- DBT DAGs retry failed tasks 2 times with 5-minute delays
- DLQ DAG retries 2 times with 5-minute delays
- Great Expectations failures log warnings but don't fail the DAG (`|| echo "WARNING" && exit 0`)

## Related Modules

- **[tools/dbt/models/staging](../../../tools/dbt/models/staging/CONTEXT.md)** — Silver layer DBT models that Silver DAG executes; transforms Bronze events into clean staging tables
- **[tools/dbt/models/marts](../../../tools/dbt/models/marts/CONTEXT.md)** — Gold layer dimensional models that Gold DAG builds; creates star schema for analytics
- **[tools/great-expectations](../../../tools/great-expectations/CONTEXT.md)** — Validation checkpoints executed after DBT runs; ensures data quality at each layer
- **[services/bronze-ingestion](../../bronze-ingestion/CONTEXT.md)** — Populates Bronze Delta tables that DAGs monitor and transform; DLQ tables track ingestion failures
