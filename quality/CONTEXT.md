# CONTEXT.md — Quality

## Purpose

Data validation layer using Great Expectations to enforce quality contracts on lakehouse tables (Silver staging and Gold layers). Validates schema conformance, business rules, and data integrity constraints across the medallion architecture.

## Responsibility Boundaries

- **Owns**: Expectation suite definitions for all lakehouse tables, checkpoint configurations for Silver and Gold validations, Python wrappers for GE 1.x CLI operations
- **Delegates to**: Spark Thrift Server for data access, DBT for data transformation, Airflow/MWAA for validation orchestration
- **Does not handle**: Data transformation (DBT's role), data storage (MinIO/S3), or validation scheduling (Airflow's role)

## Key Concepts

**Expectation Suite**: JSON files defining validation rules for a specific table. Located in `gx/expectations/` organized by layer (silver/, gold/dimensions/, gold/facts/, gold/aggregates/).

**Checkpoint**: YAML configuration that groups multiple validations together. Two checkpoints exist: `silver_validation` (8 staging tables) and `gold_validation` (12 business tables).

**Datasource**: Configured as `rideshare_spark` using SparkDFExecutionEngine to connect to Spark Thrift Server with S3A access to MinIO (localhost:9000).

**GE 1.x Migration**: Great Expectations 1.x removed CLI commands, so custom Python scripts (`run_checkpoint.py`, `build_data_docs.py`) provide command-line interfaces.

## Non-Obvious Details

Validations reference tables via fully-qualified names (e.g., `silver_staging.stg_trips`, `gold_facts.fact_trips`) but actual execution requires a live Spark Thrift Server connection. The `test_connection.py` script can verify configuration without live data.

Expectation suites encode domain knowledge: trip states must match the simulation engine's 10-state machine, surge multipliers constrained to 1.0-2.5x range, distance/duration sanity checks reflect São Paulo geography.

Store backends use filesystem (not cloud) with validation results in `uncommitted/` directory (gitignored) while expectation suites in `expectations/` are version-controlled as data contracts.
