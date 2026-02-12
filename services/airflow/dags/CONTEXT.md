# CONTEXT.md — Airflow DAGs

## Purpose

Orchestrates the data pipeline transformations and quality checks for the rideshare medallion lakehouse architecture. Manages the Bronze → Silver → Gold transformation lifecycle with DBT, monitors data quality with Great Expectations, and tracks errors in dead-letter queues (DLQ).

## Responsibility Boundaries

- **Owns**: Scheduling and execution of DBT transformations, Great Expectations validations, and DLQ monitoring
- **Delegates to**: DBT for SQL transformations (`/opt/dbt`), Great Expectations for data validation (`/opt/great-expectations`), Spark Thrift Server for DLQ queries
- **Does not handle**: Direct data processing (done by Spark Structured Streaming), schema evolution, or Kafka topic management

## Key Concepts

**Layer Transformation Schedules**
- Silver layer runs hourly with Bronze freshness checks
- Gold layer runs daily with dependency ordering: dimensions → facts → aggregates

**DLQ Monitoring**
- Queries 8 DLQ Delta tables every 15 minutes via PyHive/Spark Thrift Server
- Uses branching logic: threshold exceeded → alert, otherwise → no-op
- Threshold: 10 errors across all tables in 15-minute window

## Non-Obvious Details

**Silver DAG Task Flow**
1. Check Bronze freshness (placeholder - always passes)
2. Run DBT models tagged `silver`
3. Run DBT tests on Silver models
4. Run Great Expectations `silver_validation` checkpoint (continues on failure with warning)

**Gold DAG Task Flow**
1. Build dimension tables (`tag:dimensions`)
2. Build fact tables (`tag:facts`) - depends on dimensions
3. Build aggregates (`tag:aggregates`) - depends on facts
4. Run all Gold tests (`tag:gold`)
5. Run Great Expectations `gold_validation` checkpoint
6. Generate Great Expectations data documentation

**DLQ Monitoring Implementation**
- Uses PyHive to query DLQ tables via Trino or Spark Thrift Server
- Default connection: Trino at `trino:8080` (HTTP)
- Optional: Spark Thrift Server at `spark-thrift-server:10000` with `LDAP` auth (requires spark-testing profile)
- Gracefully handles missing tables (expected on first run)
- Uses XCom to pass error counts between tasks for branching logic

**Error Handling**
- DBT DAGs retry failed tasks 2 times with 5-minute delays
- DLQ DAG retries 2 times with 5-minute delays
- Great Expectations failures log warnings but don't fail the DAG (`|| echo "WARNING" && exit 0`)
