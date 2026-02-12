#!/usr/bin/env python3
"""Create Bronze sample tables through Spark Thrift Server for testing"""

import os

from pyhive import hive

# Connect to Spark Thrift Server
conn = hive.Connection(
    host="localhost",
    port=10000,
    database="default",
    auth="LDAP",
    username=os.getenv("HIVE_LDAP_USERNAME", "admin"),
    password=os.getenv("HIVE_LDAP_PASSWORD", "admin"),
)
cursor = conn.cursor()

print("Creating Bronze tables as PARQUET for testing...")

# Drop existing tables
for table in [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
]:
    cursor.execute(f"DROP TABLE IF EXISTS {table}")
    print(f"Dropped {table} if it existed")

# Create bronze_trips as PARQUET
print("Creating bronze_trips...")
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
    'Z01' AS pickup_zone_id,
    'Z02' AS dropoff_zone_id,
    1.2 AS surge_multiplier,
    25.50 AS fare,
    CAST(NULL AS STRING) AS driver_id,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:00:06' AS TIMESTAMP)
UNION ALL
SELECT
    'trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:05:01' AS TIMESTAMP)
UNION ALL
SELECT
    'trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
    ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
    CAST('2026-01-15 10:15:01' AS TIMESTAMP)
"""
)
print("✓ bronze_trips created")

# Create bronze_gps_pings as PARQUET
print("Creating bronze_gps_pings...")
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
UNION ALL
SELECT
    'gps-003', 'rider', 'R001', CAST('2026-01-15 10:00:00' AS TIMESTAMP),
    ARRAY(-23.550, -46.650), 3.0, NULL, NULL, NULL, NULL,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP)
"""
)
print("✓ bronze_gps_pings created")

# Create bronze_driver_status as PARQUET
print("Creating bronze_driver_status...")
cursor.execute(
    """
CREATE TABLE bronze_driver_status
STORED AS PARQUET
AS SELECT
    'status-001' AS event_id,
    'D001' AS driver_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    'idle' AS new_status,
    CAST(NULL AS STRING) AS previous_status,
    'manual' AS trigger,
    ARRAY(-23.545, -46.645) AS location,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'status-002', 'D001', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'dispatched', 'idle', 'trip_matched',
    ARRAY(-23.545, -46.645),
    CAST('2026-01-15 10:00:06' AS TIMESTAMP)
UNION ALL
SELECT
    'status-003', 'D001', CAST('2026-01-15 10:00:30' AS TIMESTAMP), 'en_route_to_pickup', 'dispatched', 'trip_accepted',
    ARRAY(-23.547, -46.647),
    CAST('2026-01-15 10:00:31' AS TIMESTAMP)
"""
)
print("✓ bronze_driver_status created")

# Create bronze_surge_updates as PARQUET
print("Creating bronze_surge_updates...")
cursor.execute(
    """
CREATE TABLE bronze_surge_updates
STORED AS PARQUET
AS SELECT
    'surge-001' AS event_id,
    'Z01' AS zone_id,
    CAST('2026-01-15 10:00:00' AS TIMESTAMP) AS timestamp,
    1.0 AS previous_multiplier,
    1.2 AS new_multiplier,
    10 AS available_drivers,
    15 AS pending_requests,
    60 AS calculation_window_seconds,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP) AS _ingested_at
UNION ALL
SELECT
    'surge-002', 'Z01', CAST('2026-01-15 10:01:00' AS TIMESTAMP), 1.2, 1.5, 8, 20, 60,
    CAST('2026-01-15 10:01:01' AS TIMESTAMP)
UNION ALL
SELECT
    'surge-003', 'Z02', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.0, 15, 10, 60,
    CAST('2026-01-15 10:00:01' AS TIMESTAMP)
"""
)
print("✓ bronze_surge_updates created")

# Verify tables
cursor.execute("SHOW TABLES")
tables = [row[1] for row in cursor.fetchall()]
print(f"\n✓ All tables created successfully: {tables}")

# Verify row counts
print("\nRow counts:")
for table in [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")

cursor.close()
conn.close()
