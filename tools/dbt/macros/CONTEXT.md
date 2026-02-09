# CONTEXT.md — DBT Macros

## Purpose

Custom DBT macros that handle Delta Lake-specific edge cases and enforce medallion architecture database naming conventions for the lakehouse data pipeline.

## Responsibility Boundaries

- **Owns**: Compile-time logic for safe Delta table access and schema name generation
- **Delegates to**: DBT runtime for macro expansion, Spark for query execution
- **Does not handle**: Model-level transformations, data quality checks, or incremental logic beyond empty table guards

## Key Concepts

**Empty Source Guard** — Query-time pattern that prevents `DeltaAnalysisException` when reading Delta tables that have no columns. Uses UNION ALL with typed NULL columns and `WHERE 1=0` to maintain schema compatibility.

**Delta Source** — Generates Delta table path syntax for Bronze layer sources stored in S3 (e.g., `delta.`s3a://rideshare-bronze/bronze_trips/``). Falls back to standard `source()` function for non-bronze sources.

**Schema Name Override** — Bypasses DBT's default `target.schema` prefix to map custom schema names directly to Spark database names (e.g., `silver`, `gold`), enforcing clean lakehouse layer separation.

## Non-Obvious Details

The `source_with_empty_guard` macro uses a UNION ALL pattern with `WHERE 1=0` to handle empty Delta tables gracefully. It always attempts to read from the Delta path in S3, but the union with typed NULL columns ensures the query succeeds even if the table has no schema yet. This is a query-execution pattern, not a compile-time check.

The `generate_schema_name` macro ignores DBT's standard schema concatenation pattern (which would create `target.schema + custom_schema`) and instead uses the custom schema name directly as the database name. This is specific to dbt-spark and necessary for the medallion architecture.

## Related Modules

- **[tools/dbt/models](../models/CONTEXT.md)** — Uses these macros throughout staging and mart models for safe Bronze table access
- **[tools/dbt/models/staging](../models/staging/CONTEXT.md)** — Primary consumer of empty source guard macro for parsing Bronze JSON
