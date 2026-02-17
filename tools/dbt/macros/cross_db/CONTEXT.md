# CONTEXT.md — Cross-Database Macros

## Purpose

Database abstraction layer that enables DBT models to run on multiple SQL execution engines (DuckDB for local development, Spark/Glue for production) without code changes. Provides unified interfaces for SQL functions with different syntax across database engines.

## Responsibility Boundaries

- **Owns**: Database-specific function translation, adapter dispatch logic for DuckDB/Spark/Glue
- **Delegates to**: DBT's `adapter.dispatch()` for runtime engine detection, staging models for actual data transformation
- **Does not handle**: Business logic, data validation, or incremental processing strategy

## Key Concepts

**Adapter Dispatch** — DBT pattern using `adapter.dispatch('macro_name', 'rideshare')` to select database-specific implementation at compile time. Each macro provides `duckdb__*`, `spark__*`, `glue__*`, and `default__*` variants.

**Engine Compatibility Matrix** — DuckDB for local testing (fast iteration), Spark Thrift Server for CI validation, AWS Glue/Spark for production. All macros guarantee identical query semantics across engines.

**Format Translation** — Some macros (e.g., `format_date`) translate format strings between engine conventions (Spark's `yyyy-MM-dd` to DuckDB's `%Y-%m-%d`).

## Non-Obvious Details

The `safe_array_element` macro uses 1-based indexing for both DuckDB and Spark to maintain consistency, even though DuckDB's `list_extract()` natively supports both 0-based and 1-based indexing.

The `day_of_week` macro normalizes output to 1=Sunday standard by adding 1 to DuckDB's `dayofweek()` result (which returns 0=Sunday), matching Spark's native behavior.

The `glue__*` implementations always delegate to `spark__*` variants because AWS Glue uses Spark SQL syntax.

All macros use the `rideshare` namespace in `adapter.dispatch()` to avoid conflicts with external DBT packages.

## Related Modules

- **[tools/dbt/models/staging](../../models/staging/CONTEXT.md)** — Staging models that use these macros for cross-database date/time functions and JSON parsing
- **[tools/dbt/models/marts](../../models/marts/CONTEXT.md)** — Marts models that use these macros for temporal joins and aggregations
- **[services/openldap](../../../../services/openldap/CONTEXT.md)** — OpenLDAP provides authentication when DBT targets Spark Thrift Server in spark-testing profile
