# CONTEXT.md — Dimensions

## Purpose

Provides dimension tables for the Gold layer star schema, implementing both static reference dimensions and slowly changing dimensions (SCD Type 2) to track historical changes in driver profiles and payment methods.

## Responsibility Boundaries

- **Owns**: Surrogate key generation, SCD Type 2 validity windows (`valid_from`/`valid_to`), current record flagging, dimension table materialization from staging sources
- **Delegates to**: Staging models for cleansed source data, fact tables for temporal join logic, DBT generic tests for SCD validity validation
- **Does not handle**: Business logic transformations (done in staging), schema evolution (handled by Bronze layer), dimension deduplication (done upstream in staging)

## Key Concepts

**SCD Type 2**: `dim_drivers` and `dim_payment_methods` track historical changes using temporal validity windows. Each change creates a new row with `valid_from` (change timestamp), `valid_to` (next change or `9999-12-31`), and `current_flag` (true for active version). Surrogate keys combine natural key + `valid_from` for uniqueness across versions.

**Current State Dimensions**: `dim_riders` captures only the latest snapshot per rider using `row_number()` window function over `timestamp desc`. No historical tracking as rider profile changes are not analytically relevant.

**Static Reference Dimension**: `dim_zones` materializes geographic zone metadata from DBT seed data. Includes Sao Paulo-specific validations on centroid coordinates (latitude between -25 and -23, longitude between -47 and -46).

**Time Dimension**: `dim_time` generates a date spine from 2024-01-01 to 2026-12-31 with pre-calculated date attributes (day_of_week in ISO format, is_weekend flag, quarter). Uses DBT Utils `date_spine()` macro.

## Non-Obvious Details

**Surrogate Key Generation**: All dimensions use `dbt_utils.generate_surrogate_key()` to create deterministic hash-based keys. SCD Type 2 dimensions include `valid_from` in the hash to ensure uniqueness across temporal versions.

**Temporal Join Pattern**: Fact tables join SCD Type 2 dimensions using `fact.event_time >= dim.valid_from AND fact.event_time < dim.valid_to` to retrieve the dimension state valid at the time of the fact event.

**Day of Week Normalization**: `dim_time` converts database-specific day_of_week (1=Sunday) to ISO-8601 format (1=Monday, 7=Sunday) using case logic. Weekend flag also uses normalized values (1, 7).

**Payment Method Deduplication**: `dim_payment_methods` derives from `stg_riders` (not a separate staging table) and tracks changes to `payment_method_type` and `payment_method_masked` fields with SCD Type 2.

**SCD Validity Test**: Custom generic test `scd_validity` validates no overlapping time periods for the same natural key and ensures `valid_from < valid_to`. Applied to both `dim_drivers` and `dim_payment_methods`.

## Related Modules

- **[tools/dbt/models/staging](../../staging/CONTEXT.md)** — Staging models that provide cleansed source data for dimension building
- **[tools/dbt/models/marts/facts](../facts/CONTEXT.md)** — Fact tables that join to these dimensions using temporal join patterns for SCD Type 2
- **[tools/dbt/tests/generic](../../../tests/generic/CONTEXT.md)** — Custom scd_validity test macro that validates SCD Type 2 implementation
- **[tools/great-expectations/gx/expectations/gold/dimensions](../../../../great-expectations/gx/expectations/gold/dimensions/CONTEXT.md)** — Data quality expectations validating dimension integrity
