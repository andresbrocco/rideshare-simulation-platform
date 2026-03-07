# CONTEXT.md — Test Data

## Purpose

Provides mock Bronze-layer views that mirror the schema of real Bronze Delta tables, allowing DBT staging models (`stg_driver_status`, `stg_gps_pings`) to run against controlled seed data without a live Kafka pipeline or Bronze ingestion stack.

## Responsibility Boundaries

- **Owns**: Schema-compatible Bronze view definitions backed by seed CSVs
- **Delegates to**: DBT seeds (`seed_zombie_driver_test`, `seed_gps_outlier_test`, `seed_impossible_speed_test`) for actual fixture rows
- **Does not handle**: Real event ingestion, Bronze table registration, or production data paths

## Key Concepts

These models exist because seeds store lat/lon as separate columns, while real Bronze tables store `location` as an array. Each model applies `array(latitude, longitude) as location` to bridge that difference, making test data structurally identical to what staging models consume in production.

## Non-Obvious Details

- `bronze_gps_pings` unions three separate seed fixtures (`seed_gps_outlier_test`, `seed_impossible_speed_test`, `seed_zombie_driver_test`) into a single view. The zombie driver seed contains both GPS events (`evt_gps%`) and status events (`evt_status%`); a `where event_id like 'evt_gps%'` filter isolates only the GPS rows to prevent duplication.
- Both models are `materialized='view'`. Per project convention, DBT views cannot be registered as Trino Delta tables, so these are test-only and are never registered in `register-trino-tables.py`.
- These models shadow the names of real Bronze tables (`bronze_driver_status`, `bronze_gps_pings`). When running DBT tests with `--select test_data`, staging models transparently consume these mocks via `ref()` resolution instead of the actual Delta tables.
