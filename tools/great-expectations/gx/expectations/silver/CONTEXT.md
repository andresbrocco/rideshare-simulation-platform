# CONTEXT.md — Silver Expectations

## Purpose

Great Expectations suite definitions that validate Silver layer staging tables after Bronze-to-Silver transformation. Each JSON file encodes the data contract for one `stg_*` table, asserting nullability constraints, uniqueness of event identifiers, domain value sets, numeric bounds, and cross-column invariants.

## Responsibility Boundaries

- **Owns**: Data quality rules for all eight Silver staging tables (`stg_drivers`, `stg_riders`, `stg_trips`, `stg_driver_status`, `stg_gps_pings`, `stg_payments`, `stg_ratings`, `stg_surge_updates`)
- **Delegates to**: The Great Expectations runtime (called from Airflow DAGs) to execute suites against Trino-accessible Delta tables
- **Does not handle**: Bronze-layer validation, Gold-layer validation (see `expectations/gold/`), or the transformation logic itself (owned by DBT Silver models)

## Key Concepts

- **`mostly` threshold**: Several spatial and numeric checks use `"mostly": 0.99` or `"mostly": 0.95` rather than 100%, intentionally tolerating a small fraction of outliers. This prevents pipeline failures from edge-case simulation artifacts while still catching systematic data corruption.
- **Event-level uniqueness**: All suites assert `event_id` is unique and non-null. Silver tables are event-log style (one row per event), not entity snapshots, so duplicate `event_id` values indicate deduplication failure in the Bronze → Silver step.
- **Geobounding box**: Latitude/longitude checks are bounded to roughly the Sao Paulo metro area (`lat: -23.8 to -23.3`, `lon: -46.9 to -46.3`). Any coordinate outside this range is treated as a geospatial anomaly.

## Non-Obvious Details

- **`silver_stg_driver_status` status set** uses `["online", "offline", "en_route"]`, which is a simplified subset — the simulation engine internally tracks more granular states (`available`, `driving_closer_to_home`, etc.) that are mapped down before Silver landing.
- **`silver_stg_trips` trip state set** encodes the full trip lifecycle state machine: `requested → offer_sent → (offer_expired | offer_rejected | matched) → driver_en_route → driver_arrived → started → (completed | cancelled)`. Any value outside this set indicates an unrecognized transition.
- **`silver_stg_payments` cross-column invariant**: `fare_amount >= platform_fee_amount` is enforced via `expect_column_pair_values_a_to_be_greater_than_b` (with `or_equal: true`). This guards against a fee-exceeds-fare condition that would indicate a calculation bug.
- **Surge multiplier range 1.0–2.5**: Both `silver_stg_trips` and `silver_stg_surge_updates` enforce this same range. The cap of 2.5 is a simulation business rule, not a GE default.
- **License plate regex** (`^[A-Z]{3}-[0-9]{4}$`) reflects Brazilian Mercosul plate format. Applied with `mostly: 0.95` to tolerate any synthetic anomalies in generated data.
- **`silver_stg_payments` and `silver_stg_ratings`** may have zero rows early in a simulation run because payments and ratings are only emitted after trip completion. The Airflow DAG that invokes these suites should tolerate empty-table results as a valid state.

## Related Modules

- [tools/dbt/models/staging](../../../../dbt/models/staging/CONTEXT.md) — Dependency — Silver layer JSON parsing, deduplication, validation filtering, and anomaly dete...
- [tools/great-expectations/gx](../../CONTEXT.md) — Dependency — Great Expectations project root defining the GX context configuration, datasourc...
- [tools/great-expectations/gx/expectations](../CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/gold](../gold/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
- [tools/great-expectations/gx/expectations/gold/dimensions](../gold/dimensions/CONTEXT.md) — Shares Data Quality and Validation domain (mostly threshold)
