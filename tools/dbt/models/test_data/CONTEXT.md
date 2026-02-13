# CONTEXT.md — Test Data

## Purpose

Mock Bronze layer tables that enable unit testing of anomaly detection models without requiring actual Kafka ingestion or S3 Bronze data. Transforms seed CSV data into Bronze-compatible views with the same schema as production Bronze tables.

## Responsibility Boundaries

- **Owns**: Schema transformation from seed CSV format (separate lat/lon columns) to Bronze format (location array), union logic combining multiple test seeds into single Bronze tables
- **Delegates to**: DBT seed mechanism for loading CSV test data, anomaly detection models for validation logic
- **Does not handle**: Production data ingestion, actual Bronze persistence, seed data generation (seeds are manually authored)

## Key Concepts

**Bronze Simulation Pattern**: Test models reference seed data via `ref('seed_*')` and reshape columns to match production Bronze schema. This allows staging and anomaly models to reference `ref('bronze_gps_pings')` in tests with identical behavior to production `delta_source()` queries.

**Test Seed Naming**: Seeds follow pattern `seed_{scenario}_test` where scenario describes the anomaly type being validated (zombie_driver, gps_outlier, impossible_speed). Each seed contains driver/rider events that trigger specific anomaly detection rules.

**Schema Adaptation**: Seed CSVs use separate `latitude` and `longitude` columns for readability, while Bronze expects `location` array. Models use `array(latitude, longitude)` to bridge this gap.

## Non-Obvious Details

**Union All Pattern**: `bronze_gps_pings.sql` unions three different seed tables to provide GPS events for multiple test scenarios. This allows anomaly detection tests to run against a unified mock Bronze table while keeping seed data organized by scenario.

**Event ID Filtering**: `bronze_driver_status.sql` filters `seed_zombie_driver_test` by `event_id like 'evt_status%'` because the seed contains both status events and GPS events. The GPS events are extracted separately in `bronze_gps_pings.sql` using `event_id like 'evt_gps%'`.

**Test Enablement**: Associated test files (`tests/test_zombie_driver_detection.sql`, etc.) are disabled by default with `enabled=false` config because they require specific seed data to be loaded. Tests are run manually during development when validating anomaly detection logic changes.

**Entity Type Injection**: For zombie driver GPS events, `bronze_gps_pings.sql` hardcodes `'driver' as entity_type` because the seed schema maps `driver_id` to `entity_id` but lacks an explicit entity_type column.

## Related Modules

- **[tools/dbt/tests](../../tests/CONTEXT.md)** — Contains singular tests that use these mock Bronze tables to validate anomaly detection logic
- **[tools/dbt/models/staging](../staging/CONTEXT.md)** — Staging models reference Bronze tables; test data models mock Bronze for isolated testing
- **[services/bronze-ingestion](../../../../services/bronze-ingestion/CONTEXT.md)** — Production Bronze ingestion that these test models simulate for unit testing purposes
