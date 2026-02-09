-- Create sample Bronze tables for testing staging models using CTAS

-- Drop tables if they exist
DROP TABLE IF EXISTS bronze_trips;
DROP TABLE IF EXISTS bronze_gps_pings;
DROP TABLE IF EXISTS bronze_driver_status;
DROP TABLE IF EXISTS bronze_surge_updates;

-- Create bronze_trips table with sample data
CREATE TABLE bronze_trips
USING delta
AS SELECT
    'trip-001' AS event_id,
    'trip.requested' AS event_type,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    'T001' AS trip_id,
    'R001' AS rider_id,
    ARRAY(-23.550, -46.650) AS pickup_location,
    ARRAY(-23.560, -46.660) AS dropoff_location,
    'Z01' AS pickup_zone_id,
    'Z02' AS dropoff_zone_id,
    1.2 AS surge_multiplier,
    25.50 AS fare,
    CAST(NULL AS STRING) AS driver_id,
    CAST(NULL AS INT) AS offer_sequence,
    CAST(NULL AS STRING) AS cancelled_by,
    CAST(NULL AS STRING) AS cancellation_reason,
    CAST(NULL AS STRING) AS cancellation_stage,
    CAST(NULL AS ARRAY<ARRAY<DOUBLE>>) AS route,
    CAST(NULL AS ARRAY<ARRAY<DOUBLE>>) AS pickup_route,
    CAST(NULL AS INT) AS route_progress_index,
    CAST(NULL AS INT) AS pickup_route_progress_index,
    'sess1' AS session_id,
    'corr1' AS correlation_id,
    'caus1' AS causation_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at,
    0 AS _kafka_partition,
    CAST(1000 AS BIGINT) AS _kafka_offset
UNION ALL
SELECT
    'trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'sess1', 'corr2', 'caus2',
    CAST('2026-01-15 10:00:06' AS TIMESTAMP), 0, CAST(1001 AS BIGINT)
UNION ALL
SELECT
    'trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'sess1', 'corr3', 'caus3',
    CAST('2026-01-15 10:05:01' AS TIMESTAMP), 0, CAST(1002 AS BIGINT)
UNION ALL
SELECT
    'trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'sess1', 'corr4', 'caus4',
    CAST('2026-01-15 10:15:01' AS TIMESTAMP), 0, CAST(1003 AS BIGINT);

-- Create bronze_gps_pings table with sample data
CREATE TABLE bronze_gps_pings
USING delta
AS SELECT
    'gps-001' AS event_id,
    'driver' AS entity_type,
    'D001' AS entity_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    ARRAY(-23.545, -46.645) AS location,
    5.0 AS accuracy,
    90.0 AS heading,
    15.5 AS speed,
    'T001' AS trip_id,
    'en_route_to_pickup' AS trip_state,
    CAST(NULL AS INT) AS route_progress_index,
    CAST(NULL AS INT) AS pickup_route_progress_index,
    'sess1' AS session_id,
    'corr1' AS correlation_id,
    'caus1' AS causation_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at,
    0 AS _kafka_partition,
    CAST(2000 AS BIGINT) AS _kafka_offset
UNION ALL
SELECT
    'gps-002', 'driver', 'D001', CAST('2026-01-15 10:00:10' AS TIMESTAMP),
    ARRAY(-23.547, -46.647), 5.0, 92.0, 16.0, 'T001', 'en_route_to_pickup',
    NULL, NULL, 'sess1', 'corr2', 'caus2',
    CAST('2026-01-15 10:00:11' AS TIMESTAMP), 0, CAST(2001 AS BIGINT)
UNION ALL
SELECT
    'gps-003', 'rider', 'R001', CAST('2026-01-15 10:00:00' AS TIMESTAMP),
    ARRAY(-23.550, -46.650), 3.0, NULL, NULL, NULL, NULL,
    NULL, NULL, 'sess1', 'corr3', 'caus3',
    CAST('2026-01-15 10:00:01' AS TIMESTAMP), 0, CAST(2002 AS BIGINT);

-- Create bronze_driver_status table with sample data
CREATE TABLE bronze_driver_status
USING delta
AS SELECT
    'status-001' AS event_id,
    'D001' AS driver_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    'idle' AS new_status,
    'manual' AS trigger,
    ARRAY(-23.545, -46.645) AS location,
    CAST(NULL AS STRING) AS previous_status,
    'sess1' AS session_id,
    'corr1' AS correlation_id,
    'caus1' AS causation_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at,
    0 AS _kafka_partition,
    CAST(3000 AS BIGINT) AS _kafka_offset
UNION ALL
SELECT
    'status-002', 'D001', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'dispatched', 'trip_matched',
    ARRAY(-23.545, -46.645), 'idle', 'sess1', 'corr2', 'caus2',
    CAST('2026-01-15 10:00:06' AS TIMESTAMP), 0, CAST(3001 AS BIGINT)
UNION ALL
SELECT
    'status-003', 'D001', CAST('2026-01-15 10:00:30' AS TIMESTAMP), 'en_route_to_pickup', 'trip_accepted',
    ARRAY(-23.547, -46.647), 'dispatched', 'sess1', 'corr3', 'caus3',
    CAST('2026-01-15 10:00:31' AS TIMESTAMP), 0, CAST(3002 AS BIGINT);

-- Create bronze_surge_updates table with sample data
CREATE TABLE bronze_surge_updates
USING delta
AS SELECT
    'surge-001' AS event_id,
    'Z01' AS zone_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    1.0 AS previous_multiplier,
    1.2 AS new_multiplier,
    10 AS available_drivers,
    15 AS pending_requests,
    60 AS calculation_window_seconds,
    'sess1' AS session_id,
    'corr1' AS correlation_id,
    'caus1' AS causation_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at,
    0 AS _kafka_partition,
    CAST(4000 AS BIGINT) AS _kafka_offset
UNION ALL
SELECT
    'surge-002', 'Z01', CAST('2026-01-15 10:01:00' AS TIMESTAMP), 1.2, 1.5, 8, 20, 60,
    'sess1', 'corr2', 'caus2',
    CAST('2026-01-15 10:01:01' AS TIMESTAMP), 0, CAST(4001 AS BIGINT)
UNION ALL
SELECT
    'surge-003', 'Z02', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.0, 15, 10, 60,
    'sess1', 'corr3', 'caus3',
    CAST('2026-01-15 10:00:01' AS TIMESTAMP), 0, CAST(4002 AS BIGINT);
