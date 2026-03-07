# CONTEXT.md — Tools

## Purpose

Houses batch data-quality and transformation tooling that operates on the medallion lakehouse after data has landed — specifically dbt for Silver→Gold SQL transformations and Great Expectations for post-transformation validation. These are orchestrated tools invoked by Airflow, not long-running services.

## Responsibility Boundaries

- **Owns**: SQL transformation logic (Silver → Gold star schema via dbt), data validation rules and checkpoint execution (Great Expectations against Silver and Gold Delta tables)
- **Delegates to**: Airflow for scheduling and orchestration, DuckDB or AWS Glue as the query execution engine, MinIO/S3 as the Delta Lake storage layer
- **Does not handle**: Raw ingestion (Bronze), streaming, real-time data, simulation logic, or service APIs

## Key Concepts

- **dbt target duality**: The dbt profile supports two targets — `duckdb` (local dev, reads Delta via DuckDB extensions) and `glue` (production, uses AWS Glue 4.0 Spark). The active target is controlled by the `DBT_RUNNER` environment variable set in Airflow.
- **GE standalone mode**: Great Expectations 1.x removed the CLI. `run_checkpoint.py` is a custom wrapper that bridges YAML-configured checkpoints to DuckDB connections. When `DUCKDB_PATH` exists (post-dbt run), GE reads from it directly; otherwise it creates `delta_scan()` views over S3 paths.
- **Tool vs service distinction**: Unlike entries under `services/`, nothing in `tools/` binds to a port or runs as a daemon. These are invoked processes with a finite lifecycle.

## Non-Obvious Details

- dbt materializes staging models as `incremental` into the `silver` schema; marts (dimensions, facts, aggregates) are full `table` refreshes in the `gold` schema.
- The `dbt_expectations` package (calogica) is a dbt package for column-level schema tests inside dbt — distinct from the standalone Great Expectations tool in `tools/great-expectations/`, which validates whole tables post-materialization.
- GE validation silently skips tables that are not yet populated (no rows) rather than failing, because `stg_ratings`/`stg_payments` may be empty early in a simulation run.

## Related Modules

- [services/airflow](../services/airflow/CONTEXT.md) — Dependency — Orchestrates medallion lakehouse pipeline: hourly Silver DBT transforms, daily G...
- [tools/dbt](dbt/CONTEXT.md) — Dependency — Silver and Gold transformation layer for the rideshare medallion lakehouse, pars...
- [tools/great-expectations](great-expectations/CONTEXT.md) — Dependency — Data quality validation for Silver and Gold medallion lakehouse tables using Gre...
