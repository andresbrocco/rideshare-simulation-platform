#!/usr/bin/env python3
"""Create all Bronze tables needed for aggregate testing"""

from pyhive import hive

conn = hive.Connection(host="localhost", port=10000, database="default")
cursor = conn.cursor()

print("Dropping existing Bronze tables and views...")
for table in [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_payments",
    "bronze_ratings",
    "bronze_drivers",
    "bronze_riders",
]:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"✓ Dropped TABLE {table}")
    except Exception:
        try:
            cursor.execute(f"DROP VIEW IF EXISTS {table}")
            print(f"✓ Dropped VIEW {table}")
        except Exception:
            print(f"  {table} did not exist")

# Create bronze_trips
print("\nCreating bronze_trips...")
cursor.execute(
    """
CREATE TABLE bronze_trips
STORED AS PARQUET
AS SELECT
    'trip-001' AS event_id,
    'trip.requested' AS event_type,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    'T001' AS trip_id,
    'R001' AS rider_id,
    ARRAY(-23.550, -46.650) AS pickup_location,
    ARRAY(-23.560, -46.660) AS dropoff_location,
    'PIN' AS pickup_zone_id,
    'PIE' AS dropoff_zone_id,
    1.2 AS surge_multiplier,
    25.50 AS fare,
    CAST(NULL AS STRING) AS driver_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:00:06' AS TIMESTAMP)
UNION ALL
SELECT
    'trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:05:01' AS TIMESTAMP)
UNION ALL
SELECT
    'trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:15:01' AS TIMESTAMP)
"""
)
print("✓ bronze_trips created")

# Create bronze_gps_pings
print("\nCreating bronze_gps_pings...")
cursor.execute(
    """
CREATE TABLE bronze_gps_pings
STORED AS PARQUET
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
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'gps-002', 'driver', 'D001', CAST('2026-01-15 10:00:10' AS TIMESTAMP),
    ARRAY(-23.547, -46.647), 5.0, 92.0, 16.0, 'T001', 'en_route_to_pickup',
    CAST('2026-01-15 10:00:11' AS TIMESTAMP)
"""
)
print("✓ bronze_gps_pings created")

# Create bronze_driver_status
print("\nCreating bronze_driver_status...")
cursor.execute(
    """
CREATE TABLE bronze_driver_status
STORED AS PARQUET
AS SELECT
    'status-001' AS event_id,
    'D001' AS driver_id,
    CAST('2026-01-15 09:00:00' AS TIMESTAMP) AS timestamp,
    'online' AS new_status,
    CAST(NULL AS STRING) AS previous_status,
    'manual' AS trigger,
    ARRAY(-23.545, -46.645) AS location,
    CAST('2026-01-15 09:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'status-002', 'D001', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'idle', 'online', 'automatic',
    ARRAY(-23.545, -46.645),
    CAST('2026-01-15 10:00:01' AS TIMESTAMP)
UNION ALL
SELECT
    'status-003', 'D001', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'en_route', 'idle', 'trip_matched',
    ARRAY(-23.545, -46.645),
    CAST('2026-01-15 10:00:06' AS TIMESTAMP)
UNION ALL
SELECT
    'status-004', 'D001', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'on_trip', 'en_route', 'trip_started',
    ARRAY(-23.550, -46.650),
    CAST('2026-01-15 10:05:01' AS TIMESTAMP)
UNION ALL
SELECT
    'status-005', 'D001', CAST('2026-01-15 17:00:00' AS TIMESTAMP), 'offline', 'idle', 'manual',
    ARRAY(-23.555, -46.655),
    CAST('2026-01-15 17:00:01' AS TIMESTAMP)
"""
)
print("✓ bronze_driver_status created")

# Create bronze_surge_updates
print("\nCreating bronze_surge_updates...")
cursor.execute(
    """
CREATE TABLE bronze_surge_updates
STORED AS PARQUET
AS SELECT
    'surge-001' AS event_id,
    'PIN' AS zone_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    1.0 AS previous_multiplier,
    1.2 AS new_multiplier,
    10 AS available_drivers,
    15 AS pending_requests,
    60 AS calculation_window_seconds,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'surge-002', 'PIN', CAST('2026-01-15 10:30:00' AS TIMESTAMP), 1.2, 1.5, 8, 20, 60,
    CAST('2026-01-15 10:30:01' AS TIMESTAMP)
UNION ALL
SELECT
    'surge-003', 'PIN', CAST('2026-01-15 10:45:00' AS TIMESTAMP), 1.5, 1.8, 6, 25, 60,
    CAST('2026-01-15 10:45:01' AS TIMESTAMP)
UNION ALL
SELECT
    'surge-004', 'PIE', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.0, 15, 10, 60,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP)
"""
)
print("✓ bronze_surge_updates created")

# Create bronze_payments
print("\nCreating bronze_payments...")
cursor.execute(
    """
CREATE TABLE bronze_payments
STORED AS PARQUET
AS SELECT
    'payment-001' AS event_id,
    'PAY001' AS payment_id,
    'T001' AS trip_id,
    CAST('2026-01-15 10:16:00' AS TIMESTAMP) AS timestamp,
    'R001' AS rider_id,
    'D001' AS driver_id,
    'credit_card' AS payment_method_type,
    '****1234' AS payment_method_masked,
    25.50 AS fare_amount,
    25.0 AS platform_fee_percentage,
    6.38 AS platform_fee_amount,
    19.12 AS driver_payout_amount,
    CAST('2026-01-15 10:16:01' AS TIMESTAMP) AS _ingested_at
"""
)
print("✓ bronze_payments created")

# Create bronze_ratings
print("\nCreating bronze_ratings...")
cursor.execute(
    """
CREATE TABLE bronze_ratings
STORED AS PARQUET
AS SELECT
    'rating-001' AS event_id,
    'T001' AS trip_id,
    CAST('2026-01-15 10:20:00' AS TIMESTAMP) AS timestamp,
    'rider' AS rater_type,
    'R001' AS rater_id,
    'driver' AS ratee_type,
    'D001' AS ratee_id,
    5.0 AS rating,
    CAST('2026-01-15 10:20:01' AS TIMESTAMP) AS _ingested_at
"""
)
print("✓ bronze_ratings created")

# Create bronze_drivers
print("\nCreating bronze_drivers...")
cursor.execute(
    """
CREATE TABLE bronze_drivers
STORED AS PARQUET
AS SELECT
    'driver-profile-001' AS event_id,
    'D001' AS driver_id,
    CAST('2026-01-15 09:00:00' AS TIMESTAMP) AS timestamp,
    'update' AS event_type,
    'John Driver' AS name,
    'john.driver@example.com' AS email,
    '+5511987654321' AS phone,
    'Toyota' AS vehicle_make,
    'Corolla' AS vehicle_model,
    2020 AS vehicle_year,
    'ABC1234' AS vehicle_plate,
    'White' AS vehicle_color,
    CAST('2026-01-15 09:00:01' AS TIMESTAMP) AS _ingested_at
"""
)
print("✓ bronze_drivers created")

# Create bronze_riders
print("\nCreating bronze_riders...")
cursor.execute(
    """
CREATE TABLE bronze_riders
STORED AS PARQUET
AS SELECT
    'rider-profile-001' AS event_id,
    'R001' AS rider_id,
    CAST('2026-01-15 08:00:00' AS TIMESTAMP) AS timestamp,
    'update' AS event_type,
    'Jane Rider' AS name,
    'jane.rider@example.com' AS email,
    '+5511912345678' AS phone,
    CAST('2026-01-15 08:00:01' AS TIMESTAMP) AS _ingested_at
"""
)
print("✓ bronze_riders created")

# Verify row counts
print("\nVerifying row counts:")
for table in [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_payments",
    "bronze_ratings",
    "bronze_drivers",
    "bronze_riders",
]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")

cursor.close()
conn.close()

print("\n✓ All Bronze tables created successfully!")
