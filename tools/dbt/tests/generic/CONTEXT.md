# CONTEXT.md — Generic Tests

## Purpose

Custom dbt generic tests that encode domain-specific data quality rules for the rideshare medallion lakehouse. These tests are reusable Jinja macros that get applied to Gold-layer models via `schema.yml` declarations.

## Responsibility Boundaries

- **Owns**: Domain-aware validation logic not covered by dbt's built-in tests (`unique`, `not_null`, `accepted_values`, `relationships`)
- **Delegates to**: dbt test runner for execution; `schema.yml` files in each model directory for test configuration and parameterization
- **Does not handle**: Row-level data transformation, Silver/Bronze layer validation (covered by Great Expectations)

## Key Concepts

**Generic test macros**: Each `.sql` file defines a `{% test <name>(model, ...) %}` macro. dbt resolves these by matching filenames in the `tests/generic/` directory. They return rows that represent failures — zero rows means the test passes.

**SCD Type 2 validity (`test_scd_validity`)**: Validates that slowly-changing dimension records have non-overlapping, ordered validity intervals per entity. Two checks: (1) `valid_from >= valid_to` (degenerate range), (2) interval overlap between any two records for the same entity via a self-join. Applied to `dim_drivers` and `dim_payment_methods`.

**Fare math tests**: `test_fare_calculation` asserts `total_fare = base_fare * surge_multiplier` within a float tolerance. `test_fee_percentage` asserts that a fee column equals `total * expected_percentage` within tolerance. The `fact_payments` schema uses `fee_percentage` to enforce the 75/25 driver-platform split.

**Anomaly threshold (`test_anomaly_threshold`)**: Table-level count gate — fails if the model contains more rows than `max_count`. Intended for anomaly detection models where a high count signals a data quality problem.

## Non-Obvious Details

- `test_scd_validity` has a parameter named `driver_id_column` for historical reasons, but it is reused for any entity ID (e.g., `payment_method_id` in `dim_payment_methods`). The name is misleading but the logic is generic.
- The `tolerance` parameter on fare/fee tests defaults to `0.01` (one cent in BRL), which is appropriate for currency stored as float but would need adjustment for sub-cent precision requirements.
- `test_no_future_dates` uses `current_timestamp()` — this is DuckDB/Trino compatible but would need to be `NOW()` or `GETDATE()` on other adapters.
- `test_fare_calculation` and `test_fee_percentage` are defined but `test_fare_calculation` does not appear in any current `schema.yml`. It exists as a reusable test but is not yet applied.
