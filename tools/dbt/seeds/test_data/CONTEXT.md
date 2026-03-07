# CONTEXT.md — test_data (seeds)

## Purpose

Static CSV seed data providing controlled inputs for dbt anomaly detection model tests. These seeds stand in for Bronze layer tables, allowing Silver-layer anomaly queries (`anomalies_gps_outliers`, `anomalies_zombie_drivers`, `anomalies_impossible_speed`) to be exercised without a running simulation or live Kafka pipeline.

## Responsibility Boundaries

- **Owns**: Minimal, deterministic fixture rows that trigger (or deliberately avoid) each anomaly detection condition
- **Delegates to**: `models/test_data/` views (`bronze_gps_pings`, `bronze_driver_status`) that reshape seeds into the schema expected by staging models
- **Does not handle**: Silver or Gold model seeds; production data seeding; schema definitions (those live in `schema.yml` files)

## Key Concepts

- **GPS outlier detection**: Sao Paulo bounding box is roughly −24° to −23° latitude, −47° to −46° longitude. Rows with coordinates outside this box (e.g., lat −22 or lon −50) are the positive outlier cases; rows near −23.5/−46.6 are the valid control cases.
- **Impossible speed detection**: Two sequential GPS events for the same driver within a short time window. `driver_007` rows (2 min apart, large displacement) trigger the anomaly; `driver_008` rows (10 min apart, tiny displacement) do not.
- **Zombie driver detection**: A driver is "zombie" if they went online but have had no GPS ping for an extended period. `driver_001` pings at 10:05 (5 min gap — valid); `driver_002` pings at 10:15 (15 min gap — triggers zombie).

## Non-Obvious Details

- `seed_zombie_driver_test.csv` stores two event types in one file distinguished by `event_id` prefix: `evt_status_*` rows become `bronze_driver_status` entries and `evt_gps_*` rows become `bronze_gps_pings` entries. The `bronze_gps_pings` view filters by `event_id like 'evt_gps%'` to split them.
- Seeds store latitude and longitude as separate columns (`latitude`, `longitude`), but the Bronze schema uses `location ARRAY`. The `models/test_data/` views convert them via `array(latitude, longitude)` to match the interface that staging models expect.
- `seed_zombie_driver_test.csv` rows that represent GPS pings have empty `new_status`, `previous_status`, and `trigger` columns, and the view fills in synthetic `entity_type`, `accuracy`, `heading`, `speed`, `trip_id`, and `trip_state` defaults.
- There is no `schema.yml` in this seeds directory; column types are inferred by dbt from the CSV data.
