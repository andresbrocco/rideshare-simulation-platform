# CONTEXT.md — Great Expectations

## Purpose

Data quality validation layer for the medallion lakehouse. Runs expectation suites against Silver and Gold Delta tables to assert schema correctness, referential integrity, and value constraints. Produces static HTML data docs from stored validation results.

## Responsibility Boundaries

- **Owns**: Expectation suite definitions (`gx/expectations/`), checkpoint configurations (`gx/checkpoints/`), validation results store, and the CLI wrapper scripts that replace the removed GE 1.x command-line interface
- **Delegates to**: DuckDB (query execution against Delta tables), MinIO/S3 (Delta table storage), dbt (Silver/Gold table materialization)
- **Does not handle**: Data transformation, pipeline orchestration (that belongs to Airflow), or Bronze-layer validation

## Key Concepts

- **Checkpoint**: A named set of validations pairing a data asset (SQL table or view) with an expectation suite. Defined as YAML in `gx/checkpoints/`. GE 1.x removed checkpoint CLI commands, so `run_checkpoint.py` is a custom replacement.
- **Expectation suite**: A JSON file listing assertions about a specific table (e.g., column types, non-null constraints, value ranges). Stored in `gx/expectations/`.
- **Data docs**: Static HTML reports generated from stored validation results. Built by `build_data_docs.py`; output written to `gx/uncommitted/data_docs/local_site/` (gitignored).
- **Dual-mode DuckDB connection**: `run_checkpoint.py` connects to a persistent DuckDB file at `DUCKDB_PATH` when dbt has already materialized Silver/Gold schemas there. When that file is absent, it creates an in-memory DuckDB instance and registers `delta_scan()` views pointing directly to `s3://rideshare-silver/` and `s3://rideshare-gold/` — allowing validation without a dbt run.

## Non-Obvious Details

- GE 1.x dropped its CLI entirely. All three scripts (`run_checkpoint.py`, `build_data_docs.py`, `test_connection.py`) exist specifically to restore CLI-style invocation that GE no longer provides out of the box.
- The `great_expectations.yml` datasource uses `connection_string: "duckdb:///:memory:"` as a placeholder. The actual connection (with S3 credentials and Delta extensions loaded) is constructed at runtime in `run_checkpoint.py` before GE context initialization — GE picks up the pre-configured connection rather than creating its own.
- DuckDB `delta` and `httpfs` extensions must be installed and loaded at runtime; they are not bundled. On first run in a fresh environment this triggers a network download.
- `gx/uncommitted/` is gitignored and holds validation results, config variables, and data docs. Validation results persist between runs and accumulate; old results are not auto-pruned.
- The Silver table list in `run_checkpoint.py` excludes `anomalies_gps_outliers` and `anomalies_zombie_drivers` because those are dbt views (not Delta tables) and cannot be registered via `delta_scan()`.

## Related Modules

- [services/airflow](../../services/airflow/CONTEXT.md) — Reverse dependency — Provides dbt_silver_transformation (DAG), dbt_gold_transformation (DAG), delta_maintenance (DAG) (+1 more)
- [tools](../CONTEXT.md) — Reverse dependency — Consumed by this module
- [tools/dbt](../dbt/CONTEXT.md) — Dependency — Silver and Gold transformation layer for the rideshare medallion lakehouse, pars...
- [tools/great-expectations/gx](gx/CONTEXT.md) — Reverse dependency — Provides great_expectations.yml, expectations/silver/*, expectations/gold/dimensions/* (+2 more)
- [tools/great-expectations/gx/expectations](gx/expectations/CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite)
- [tools/great-expectations/gx/expectations/gold](gx/expectations/gold/CONTEXT.md) — Shares Data Quality and Validation domain (expectation suite)
- [tools/great-expectations/gx/expectations/gold/dimensions](gx/expectations/gold/dimensions/CONTEXT.md) — Reverse dependency — Provides gold_dim_drivers, gold_dim_riders, gold_dim_zones (+2 more)
