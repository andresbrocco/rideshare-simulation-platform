# CONTEXT.md — Great Expectations Configuration

## Purpose

Great Expectations data validation framework configured to validate the rideshare platform's lakehouse tables. Validates Silver staging tables and Gold layer (dimensions, facts, aggregates) against defined expectation suites.

## Responsibility Boundaries

- **Owns**: Expectation suites for all lakehouse tables, validation checkpoints for Silver and Gold layers, Spark datasource configuration with S3/Delta Lake integration
- **Delegates to**: Airflow/MWAA for validation execution scheduling, DBT for upstream data transformations
- **Does not handle**: Data transformation logic (handled by DBT), validation result alerting (handled by orchestrator)

## Key Concepts

**Expectation Suites**: JSON files defining validation rules for each table. Located in `expectations/silver/`, `expectations/gold/dimensions/`, `expectations/gold/facts/`, `expectations/gold/aggregates/`.

**Checkpoints**: YAML files grouping multiple validation batches. `silver_validation.yml` validates 8 staging tables, `gold_validation.yml` validates 5 dimensions, 5 facts, and 2 aggregates.

**Datasource**: Configured as `rideshare_spark` using SparkDFExecutionEngine with MinIO (S3-compatible) backend and Delta Lake catalog. Connects to local MinIO at `localhost:9000` with hardcoded credentials (dev only).

**Store Backends**: Expectations stored in `expectations/`, validation results in `uncommitted/validations/`, checkpoints in `checkpoints/`. Data docs generated to `uncommitted/data_docs/local_site/`.

## Non-Obvious Details

The configuration includes hardcoded MinIO credentials (`minioadmin/minioadmin`) and local endpoint (`localhost:9000`) — suitable only for development. Production deployments must override these via `config_variables_file_path` (points to `uncommitted/config_variables.yml`).

Trip state validations enforce the simulation's 10-state trip lifecycle (REQUESTED through COMPLETED/CANCELLED). Surge multiplier validations enforce platform business rules (1.0x to 2.5x range).

The `uncommitted/` directory is gitignored to prevent validation results and generated documentation from being committed to version control.
