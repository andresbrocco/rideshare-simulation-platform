# CONTEXT.md — DBT Macros

## Purpose

Custom DBT macros that handle Delta Lake-specific edge cases and enforce medallion architecture database naming conventions for the lakehouse data pipeline.

## Responsibility Boundaries

- **Owns**: Compile-time logic for safe Delta table access and schema name generation
- **Delegates to**: DBT runtime for macro expansion, Spark for query execution
- **Does not handle**: Model-level transformations, data quality checks, or incremental logic beyond empty table guards

## Key Concepts

**Empty Source Guard** — Compile-time check that prevents `DeltaAnalysisException` when reading newly-created Delta tables that have no columns. Returns typed empty result sets to maintain schema compatibility.

**Schema Name Override** — Bypasses DBT's default `target.schema` prefix to map custom schema names directly to Spark database names (e.g., `silver_staging`, `gold_facts`), enforcing clean lakehouse layer separation.

## Non-Obvious Details

The `source_with_empty_guard` macro uses `run_query()` during the execution phase to check if tables exist, then generates a UNION ALL with an empty typed result set. This allows staging models to compile successfully even when upstream Bronze tables are missing or empty.

The `generate_schema_name` macro ignores DBT's standard schema concatenation pattern (which would create `target.schema + custom_schema`) and instead uses the custom schema name directly as the database name. This is specific to dbt-spark and necessary for the medallion architecture.
