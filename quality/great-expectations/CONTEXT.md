# CONTEXT.md — Great Expectations

## Purpose

Data quality validation layer for the rideshare simulation platform's lakehouse architecture. Validates data integrity, business rules, and referential constraints across Silver (staging) and Gold (dimensional) layers using Great Expectations 1.10.0 with Spark execution engine.

## Responsibility Boundaries

- **Owns**: Expectation suite definitions (54 Silver + 119 Gold expectations), checkpoint configurations for Silver and Gold validations, data quality documentation generation
- **Delegates to**: Spark Thrift Server for data access, MinIO for Delta Lake storage, Airflow for scheduled execution
- **Does not handle**: Data transformation (handled by DBT), data ingestion (handled by Databricks Structured Streaming), alerting infrastructure (handled by Airflow)

## Key Concepts

**Expectation Suite**: JSON definitions of data quality rules organized by layer (Silver staging models, Gold dimensions/facts/aggregates). Each suite targets a specific Delta Lake table.

**Checkpoint**: Orchestrates validation runs across multiple expectation suites. Two main checkpoints exist: `silver_validation` (8 suites) and `gold_validation` (12 suites).

**Soft Failure Pattern**: Range and geo validations use `mostly` parameter (95-99% thresholds) to alert on outliers without blocking pipelines. Critical constraints (uniqueness, nullability) use hard failures.

**SCD Type 2 Validation**: Gold dimension tables (drivers, payment_methods) validate slowly changing dimension patterns with `valid_from`, `valid_to`, and `current_flag` checks.

**Datasource Configuration**: Connects to Spark via Thrift Server on localhost:10000 with S3A protocol pointing to MinIO (localhost:9000). Uses Delta Lake format with Hive metastore catalog.

## Non-Obvious Details

**GX 1.x Migration**: Great Expectations 1.10.0 removed CLI commands, so `run_checkpoint.py` and `build_data_docs.py` provide custom wrappers for command-line execution. These verify suite existence rather than running live validations during testing.

**Python Version Constraint**: Requires Python 3.10-3.12 due to Great Expectations compatibility. Python 3.14+ is not supported.

**Validation Timing**: Expectation suites are designed to run after DBT transformations complete. Silver validations run after staging models, Gold validations run after dimensional models.

**Referential Integrity**: Gold fact tables validate foreign key relationships to dimension tables, but GX does not enforce cross-table joins. These checks verify key columns are not null, not that referenced records exist.

**Test Strategy**: Test files (`tests/test_silver_expectations.py`, `tests/test_gold_expectations.py`) validate suite structure and expectation counts without requiring live database connections. They verify JSON artifacts, not data quality.

**Checkpoint Action List**: Both checkpoints store validation results and update data docs automatically. Data docs are generated in `gx/uncommitted/data_docs/local_site/` (not version controlled).

## Related Modules

- **[services/dbt](../../services/dbt/CONTEXT.md)** — Validation target; Great Expectations validates Silver staging models and Gold dimensional models created by DBT
- **[services/airflow](../../services/airflow/CONTEXT.md)** — Orchestration partner; Airflow schedules Great Expectations checkpoint runs after DBT transformations
