# CONTEXT.md — Gold Dimensions

## Purpose

Expectation suite definitions for Gold layer dimension tables in the lakehouse medallion architecture. These JSON files define data quality rules that validate dimensional model integrity, SCD Type 2 patterns, and business constraints for reference data used in star schema queries.

## Responsibility Boundaries

- **Owns**: Expectation suite definitions for 5 dimension tables (drivers, riders, zones, payment_methods, time), validation rules for surrogate keys, natural keys, SCD Type 2 attributes, and domain-specific constraints
- **Delegates to**: Great Expectations checkpoint runner for validation execution, DuckDB with delta/httpfs for data access, Gold layer DBT models for the actual dimensional data
- **Does not handle**: Validation execution (handled by checkpoints), data transformation (handled by DBT), aggregate or fact table validation (handled by sibling directories)

## Key Concepts

**Dimension Table Pattern**: Each expectation suite validates a slowly changing dimension (SCD Type 2) or static dimension table. All dimension tables have surrogate keys (`*_key`) that are unique and not null, enabling stable fact table joins.

**SCD Type 2 Validation**: Drivers and payment_methods tables track historical changes using `valid_from`, `valid_to`, and `current_flag` attributes. Expectations ensure these temporal columns are not null and current_flag is boolean.

**Natural Key Uniqueness**: Each dimension has a natural business key (`driver_id`, `rider_id`, `zone_id`, `payment_method_id`, `time_key`) that must be unique within the current version for static dimensions or across all versions for SCDs.

**Domain Constraints**: Expectations enforce business rules like Brazilian license plate format (`^[A-Z]{3}-[0-9]{4}$` with 95% compliance threshold), payment type enumeration (`credit_card`, `debit_card`, `cash`, `digital_wallet`), time dimension ranges (years 2020-2030, months 1-12), and required attributes (vehicle make/model for drivers).

## Non-Obvious Details

**Soft Failure Threshold**: License plate regex validation uses `mostly: 0.95` to allow 5% non-conformance without blocking the pipeline. This accommodates data quality issues in synthetic data generation while alerting on excessive violations.

**Time Dimension Constraints**: The time dimension validates year range 2020-2030 and standard calendar constraints (month 1-12, day 1-31, hour 0-23) to catch timestamp parsing errors or simulation clock issues.

**Geometry Column**: Zone dimension includes a `geometry` column (GeoJSON polygon) that is validated for null checks but not spatial validity. Spatial validation would require custom Great Expectations expectations.

**Date Key Format**: Time dimension has both `time_key` (primary surrogate key) and `date_key` (denormalized date identifier) as separate not-null columns, supporting both timestamp-level and date-level aggregations.

## Related Modules

- **[tools/dbt/models/marts/dimensions](../../../../../../tools/dbt/models/marts/dimensions/CONTEXT.md)** — DBT dimension table definitions that these expectation suites validate
- **[tools/great-expectations](../../../../CONTEXT.md)** — Parent GX module that orchestrates checkpoint execution of these suites
- **[tools/dbt/tests/generic](../../../../../../tools/dbt/tests/generic/CONTEXT.md)** — Complementary DBT-level tests for SCD Type 2 validation and business rules
