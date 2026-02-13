# CONTEXT.md — DBT Tests

## Purpose

Validates DBT transformation logic across the medallion architecture using singular SQL tests for dimensional model integrity, SCD Type 2 validity, and anomaly detection accuracy. Also includes Python-based manifest tests to verify documentation completeness and lineage graph correctness.

## Responsibility Boundaries

- **Owns**: Singular test queries for Gold layer validation, seed data validation patterns, manifest-based documentation tests, SCD Type 2 validity checks
- **Delegates to**: DBT core (test execution framework), schema.yml files in models/ (generic tests like unique, not_null), dbt-expectations package (advanced statistical tests)
- **Does not handle**: Generic test definitions (those live in schema.yml), actual data transformation logic (models/), test orchestration (Airflow)

## Key Concepts

### Singular Tests

SQL queries that return rows representing test failures. Tests in this directory validate cross-table business rules that cannot be expressed as generic column-level tests. Expected to return zero rows on success.

### Seed Data Validation

Tests tagged with `seed_data_validation` and `enabled=false` that require specific test entities in Bronze tables. Run explicitly with `dbt test --select tag:seed_data_validation` after seeding test data. Used to validate anomaly detection algorithms (GPS outliers, impossible speeds, zombie drivers) against known-good and known-bad test cases.

### Manifest-Based Testing

Python tests that parse `target/manifest.json` and `target/catalog.json` to validate meta-properties of the DBT project itself (documentation completeness, lineage relationships, column descriptions). Run with pytest, not `dbt test`.

### SCD Type 2 Validation

Tests that verify Slowly Changing Dimension implementation correctness by checking validity date ranges, current_flag uniqueness, and non-overlapping version windows. Critical for `dim_drivers` and `dim_payment_methods`.

## Non-Obvious Details

- **Disabled by Default**: Tests with `enabled=false` expect specific test entities and will fail on production data. They validate transformation logic, not production data quality.
- **Expected Failures**: Some tests include comments like "Expected failure: Model doesn't exist yet", indicating they were written before model implementation (TDD approach).
- **Cross-Join Pattern**: Validation tests often use `cross join` to combine multiple failure conditions into a single result set, returning rows only when any condition fails.
- **Manifest Dependency**: Python tests require running `dbt compile` or `dbt docs generate` first to populate `target/manifest.json`.
- **Hardcoded Paths**: Python tests contain absolute paths to manifest files specific to the developer's machine, which may need updating for different environments.

## Related Modules

- **[tools/dbt/tests/generic](generic/CONTEXT.md)** — Reusable test macros that can be applied to multiple models; singular tests in this directory complement generic tests
- **[tools/dbt/models/marts](../models/marts/CONTEXT.md)** — Gold layer dimensional models validated by SCD Type 2 and referential integrity tests
- **[tools/dbt/models/test_data](../models/test_data/CONTEXT.md)** — Mock Bronze tables used by seed_data_validation tests to validate anomaly detection
- **[tools/great-expectations](../../great-expectations/CONTEXT.md)** — Complementary data quality validation that runs after DBT transformations via Airflow
