# CONTEXT.md — Gold Dimensions Expectations

## Purpose

Great Expectations expectation suites that validate the structural and referential integrity of Gold-layer dimension tables in the star schema. Each JSON file maps one-to-one with a dimension table and enforces surrogate key uniqueness, nullability constraints, and domain-specific value rules.

## Responsibility Boundaries

- **Owns**: Column-level data quality assertions for all Gold dimension tables
- **Delegates to**: The Great Expectations runner (Airflow DAG) to execute suites against actual table data
- **Does not handle**: Fact table validation (separate suites), cross-table referential integrity checks, or row-count expectations

## Key Concepts

- **Surrogate key (`*_key`)**: Each dimension has a surrogate key that must be both non-null and globally unique. This is the join key used by fact tables.
- **Natural key (`*_id`)**: The business identifier from the source simulation. Uniqueness enforcement varies by dimension type (see Non-Obvious Details).
- **SCD Type 2 fields**: `valid_from`, `valid_to`, and `current_flag` appear on `dim_drivers`, `dim_riders` (implicitly), and `dim_payment_methods` — these track historical changes to slowly-changing attributes.

## Non-Obvious Details

- **Mixed SCD types in one schema**: `dim_drivers` and `dim_payment_methods` are SCD Type 2 (have `valid_from`/`valid_to`/`current_flag`). `dim_riders` enforces uniqueness on both surrogate key AND natural key `rider_id`, making it behave as a Type 1 (non-historized) dimension. `dim_zones` and `dim_time` are static reference dimensions with no versioning fields at all.
- **License plate regex tolerance**: `gold_dim_drivers` uses `mostly: 0.95` on the Brazilian plate format regex (`^[A-Z]{3}-[0-9]{4}$`), allowing up to 5% non-conforming values. This accommodates the newer Mercosul plate format (`[A-Z]{3}[0-9][A-Z][0-9]{2}`) used in Brazil since 2018.
- **Hardcoded year range**: `gold_dim_time` enforces `year` between 2020 and 2030. This will require updating when the simulation runs past 2030.
- **`dim_zones` has no SCD**: Zone geometry is treated as immutable — `zone_id` is expected to be unique (no historical versions), so `geometry` changes would require a new record rather than versioning.

## Related Modules

- [tools/dbt/models/marts](../../../../../dbt/models/marts/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
- [tools/dbt/models/marts/dimensions](../../../../../dbt/models/marts/dimensions/CONTEXT.md) — Shares SCD Type 2 and Slowly Changing Dimensions domain (scd type 2)
- [tools/dbt/models/marts/dimensions](../../../../../dbt/models/marts/dimensions/CONTEXT.md) — Shares Star Schema and Data Modeling domain (surrogate key)
- [tools/great-expectations](../../../../CONTEXT.md) — Dependency — Data quality validation for Silver and Gold medallion lakehouse tables using Gre...
- [tools/great-expectations/gx/expectations](../../CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/gold](../CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/silver](../../silver/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
