# CONTEXT.md — gx

## Purpose

The Great Expectations project root for the rideshare platform. Defines the GX context configuration (datasources, stores, data docs sites) and houses all committed expectation suites for Silver and Gold medallion layers. Validation results and data docs are excluded from version control via the `uncommitted/` gitignore pattern.

## Responsibility Boundaries

- **Owns**: GX context configuration (`great_expectations.yml`), expectation suite JSON files for Silver and Gold tables, store layout definitions
- **Delegates to**: Airflow DAGs for triggering checkpoint runs; the `tools/great-expectations/` parent for the runner script that invokes checkpoints
- **Does not handle**: Bronze layer validation (raw ingestion is validated at the schema level by Kafka Schema Registry), checkpoint execution scheduling

## Key Concepts

- **Datasource — DuckDB in-memory**: The `rideshare_duckdb` datasource uses `SqlAlchemyExecutionEngine` with `duckdb:///:memory:`. Validation runs against data loaded into an ephemeral DuckDB instance, not directly against Delta Lake or Trino. This means the runner script is responsible for loading Parquet/Delta data into DuckDB before validation executes.
- **Store layout — committed vs uncommitted**: `expectations/` and `checkpoints/` and `validation_definitions/` are committed. `uncommitted/validations/` and `uncommitted/data_docs/` are gitignored. This means expectation suites are version-controlled but per-run validation results are ephemeral.
- **Expectation suite hierarchy**: Suites are organized under `expectations/silver/` and `expectations/gold/{dimensions,facts,aggregates}/`, mirroring the DBT model namespace. Suite names use the fully qualified table prefix (e.g., `silver_stg_trips`, `gold_fact_trips`).

## Non-Obvious Details

- `create_temp_table: false` is set on the DuckDB execution engine. DuckDB's in-memory mode does not support temp tables the same way as other SQL engines; this prevents GX from attempting to create intermediate temp tables that would fail.
- The `config_variables_file_path` points to `uncommitted/config_variables.yml` (gitignored). Any credentials or environment-specific overrides go there, not in `great_expectations.yml`.
- Gold aggregates and dimensions directories have `.gitkeep` files but several suites are populated (e.g., `gold_agg_daily_driver_performance`, `gold_dim_drivers`). The `.gitkeep` pattern was retained even after suites were added, so directory presence alone does not indicate suite existence.

## Related Modules

- [tools/great-expectations](../CONTEXT.md) — Dependency — Data quality validation for Silver and Gold medallion lakehouse tables using Gre...
- [tools/great-expectations/gx/expectations/silver](expectations/silver/CONTEXT.md) — Reverse dependency — Provides silver_stg_drivers, silver_stg_riders, silver_stg_trips (+5 more)
