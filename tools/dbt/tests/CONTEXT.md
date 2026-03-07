# CONTEXT.md — DBT Tests

## Purpose

Custom singular tests for the DBT Gold layer, validating star schema structural invariants, SCD Type 2 correctness, data quality anomaly detection logic, and documentation completeness. These tests supplement schema.yml generic tests (uniqueness, not-null, accepted values) with business-rule assertions that cannot be expressed generically.

## Responsibility Boundaries

- **Owns**: Structural and business-rule assertions on Gold dimension tables, anomaly model correctness, and DBT project documentation integrity
- **Delegates to**: `schema.yml` generic tests for column-level constraints (uniqueness, not-null, accepted values), Great Expectations for Bronze/Silver data quality
- **Does not handle**: Unit testing of SQL transformation logic in isolation; pipeline orchestration or execution

## Key Concepts

**Singular tests** — DBT's file-based test format: a `.sql` file in `tests/` that returns rows on failure and zero rows on success. These differ from schema.yml `tests:` entries which are generic and reusable.

**SCD Type 2 invariants** — `test_dim_drivers_scd_type2.sql` and `test_dim_payment_methods_scd_type2.sql` assert that exactly one current record exists per entity (`current_flag = true`) and that active records carry `valid_to = 9999-12-31`. Payment methods have a subtle nuance: `current_count = 0` is valid (the entity type was fully replaced), but `current_count > 1` is always invalid.

**Seed-data validation tests** — A subset of tests is tagged `seed_data_validation` and `enabled=false` by default. They require deterministic seed data with specific entity IDs (e.g., `driver_003` through `driver_008`) to exercise anomaly detection thresholds (GPS bounding box for São Paulo, impossible speed > 200 km/h, zombie driver ping gap >= 10 minutes). Run via `dbt test --select tag:seed_data_validation --vars '{"enable_seed_tests": true}'`.

**Documentation meta-test** — `test_documentation_completeness.py` is a pytest file (not a DBT test) that reads `target/manifest.json` and `target/catalog.json` to assert all models have descriptions, key columns have descriptions, doc blocks are referenced in schema files, and the Bronze → Silver → Gold lineage chain is present in the compiled DAG. Requires `dbt compile` or `dbt docs generate` to be run first.

## Non-Obvious Details

- `test_dim_riders_current_state.sql` enforces that `dim_riders` is **not** SCD Type 2 — it is a snapshot of current state only (one row per rider), in contrast to `dim_drivers` which tracks history.
- `test_dim_zones_complete.sql` hardcodes the expectation of exactly 96 zones, derived from the São Paulo districts in `zones.geojson`. This number must be updated if the source GeoJSON changes.
- `test_dim_time_attributes.sql` uses hardcoded dates `2024-01-01` (Monday, `day_of_week=1`) and `2024-01-06` (Saturday, `day_of_week=6`) to verify weekday/weekend flag logic. The test assumes Monday-based weekday numbering.
- The `test_documentation_completeness.py` file contains absolute paths to the local machine — it is not portable across environments without modification. It is a local developer-run test, not part of the CI `dbt test` invocation.

## Related Modules

- [tools/dbt/models](../models/CONTEXT.md) — Reverse dependency — Provides stg_trips, stg_gps_pings, stg_driver_status (+24 more)
- [tools/dbt/models/marts/dimensions](../models/marts/dimensions/CONTEXT.md) — Dependency — Gold-layer dimension tables forming the dimension side of the star schema, with ...
- [tools/dbt/models/marts/facts](../models/marts/facts/CONTEXT.md) — Dependency — Gold-layer fact tables for the rideshare star schema covering completed trips, p...
- [tools/dbt/models/staging](../models/staging/CONTEXT.md) — Dependency — Silver layer JSON parsing, deduplication, validation filtering, and anomaly dete...
