# CONTEXT.md — Cross-DB Macros

## Purpose

Provides a set of dbt macros that abstract SQL dialect differences between DuckDB (local development) and Spark/Glue (production). Models call these macros instead of engine-specific SQL functions, enabling the same model code to run correctly on both targets without branching logic in business-logic SQL.

## Responsibility Boundaries

- **Owns**: All SQL dialect translation for functions that differ between DuckDB and Spark
- **Delegates to**: dbt's `adapter.dispatch` mechanism for runtime engine selection
- **Does not handle**: Business logic, data transformations beyond type/format conversion, or catalog differences between environments

## Key Concepts

Each macro follows the dbt dispatch pattern: a top-level macro calls `adapter.dispatch('macro_name', 'rideshare')`, which routes to the appropriate `duckdb__*`, `spark__*`, `glue__*`, or `default__*` implementation. The `glue__*` variants always delegate to `spark__*`, and `default__*` also delegates to `spark__*`, making Spark the fallback for any engine not explicitly overridden.

## Non-Obvious Details

- **day_of_week indexing**: DuckDB's `dayofweek()` returns 0 for Sunday, so the macro adds `+ 1` to normalize to the Spark convention (1=Sunday, 7=Saturday). Any new consumer must use this macro rather than calling `dayofweek()` directly to avoid this off-by-one discrepancy.
- **format_date format strings**: Callers always pass Spark-style format strings (e.g., `yyyy-MM-dd`, `EEEE`). The `duckdb__format_date` implementation translates these to `strftime` format codes at macro expansion time using Jinja `replace` filters. This means the format string argument is interpreted differently under each engine — do not pass strftime-style codes.
- **to_ts null safety**: DuckDB uses `try_cast` (returns NULL on parse failure) while Spark uses `to_timestamp` (raises an error on invalid input). Models relying on null-safe coercion will behave differently if ever run directly on Spark without the macro.
- **json_field path syntax**: JSONPath expressions use `$.field` syntax. DuckDB's `json_extract_string` and Spark's `get_json_object` both accept this format, but only the string-extraction variant is exposed — callers needing typed extraction must cast the result separately.
- **safe_array_element indexing**: Both DuckDB (`list_extract`) and Spark (`try_element_at`) use 1-based array indexing in these macros. DuckDB natively supports 1-based access via `list_extract`, which is also NULL-safe on out-of-bounds access.

## Related Modules

- [tools/dbt/macros](../CONTEXT.md) — Shares DBT Transformations domain (adapter.dispatch)
- [tools/dbt/models/marts](../../models/marts/CONTEXT.md) — Reverse dependency — Provides dim_drivers, dim_riders, dim_zones (+12 more)
- [tools/dbt/models/marts/dimensions](../../models/marts/dimensions/CONTEXT.md) — Reverse dependency — Provides dim_drivers, dim_riders, dim_zones (+2 more)
- [tools/dbt/models/marts/facts](../../models/marts/facts/CONTEXT.md) — Reverse dependency — Provides fact_trips, fact_payments, fact_ratings (+3 more)
- [tools/dbt/models/staging](../../models/staging/CONTEXT.md) — Reverse dependency — Provides stg_trips, stg_gps_pings, stg_driver_status (+9 more)
