# CONTEXT.md — Generic Tests

## Purpose

Reusable DBT test macros that validate domain-specific business rules and data quality constraints across multiple models. These tests extend DBT's built-in tests (unique, not_null, relationships) with custom logic for ride-sharing data validation.

## Responsibility Boundaries

- **Owns**: Domain-specific data quality test logic, validation SQL patterns, parameterized test interfaces
- **Delegates to**: DBT test framework (execution, reporting), model schemas (test invocation via schema.yml files)
- **Does not handle**: Test execution or scheduling (handled by DBT CLI/Airflow), result storage, or alerting

## Key Concepts

### Generic Tests vs Singular Tests

- **Generic tests** (this directory): Reusable parameterized tests that can be applied to any model/column by referencing them in `schema.yml` files
- **Singular tests** (`tools/dbt/tests/*.sql`): One-off SQL queries that test specific models and cannot be reused

### Test Macro Pattern

All tests follow the `{% test test_name(model, parameters...) %}` Jinja macro pattern. Tests return rows that represent validation failures. Zero rows = test passes.

## Non-Obvious Details

- **anomaly_threshold**: Validates anomaly detection models don't exceed expected counts. Used to ensure data quality checks don't generate excessive false positives.
- **scd_validity**: Enforces non-overlapping validity windows in SCD Type 2 dimensions. Validates both that `valid_from < valid_to` and that no two records for the same entity have overlapping date ranges.
- **fare_calculation**: Validates multiplicative fare calculations with configurable tolerance for floating-point precision. Used to verify `total_fare = base_fare * surge_multiplier`.
- **fee_percentage**: Validates percentage-based calculations (platform fees, driver payouts) with tolerance for rounding errors. Used in `fact_payments` to ensure 25% platform fee and 75% driver payout.
- **no_future_dates**: Prevents temporal data quality issues by ensuring timestamp columns don't contain dates beyond current time. Common validation for event ingestion pipelines.

### Tolerance Parameters

Both `fare_calculation` and `fee_percentage` accept a `tolerance` parameter (default: 0.01) to handle floating-point arithmetic precision issues without spurious test failures.

## Related Modules

- **[tools/dbt/models/marts/dimensions](../../models/marts/dimensions/CONTEXT.md)** — Dimension tables that use scd_validity test to validate SCD Type 2 implementation
- **[tools/dbt/models/marts/facts](../../models/marts/facts/CONTEXT.md)** — Fact tables that use fare_calculation and fee_percentage tests for business rule validation
- **[tools/dbt/tests](../CONTEXT.md)** — Singular tests that complement these generic tests for comprehensive validation coverage
