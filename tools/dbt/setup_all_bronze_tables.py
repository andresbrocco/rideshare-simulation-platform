#!/usr/bin/env python3
"""Create all Bronze Delta tables on MinIO for aggregate testing.

This script creates Delta tables with test data in the rideshare-bronze bucket.
It connects to Spark Thrift Server and uses Delta Lake format stored on MinIO.

Table names and schemas must match what the DBT staging models expect:
- bronze_trips
- bronze_gps_pings
- bronze_driver_status
- bronze_surge_updates
- bronze_payments
- bronze_ratings
- bronze_driver_profiles (not bronze_drivers!)
- bronze_rider_profiles (not bronze_riders!)
"""

import os

from pyhive import hive

conn = hive.Connection(
    host="localhost",
    port=10000,
    database="default",
    auth="LDAP",
    username=os.getenv("HIVE_LDAP_USERNAME", "admin"),
    password=os.getenv("HIVE_LDAP_PASSWORD", "admin"),
)
cursor = conn.cursor()

print("Dropping existing Bronze tables and views...")
tables_to_drop = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_payments",
    "bronze_ratings",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
    # Also drop old incorrect names
    "bronze_drivers",
    "bronze_riders",
]

# First, drop all as views (in case they were created as views by dbt)
for table in tables_to_drop:
    try:
        cursor.execute(f"DROP VIEW IF EXISTS {table}")
    except Exception:
        pass

# Then drop as tables
for table in tables_to_drop:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"✓ Dropped {table}")
    except Exception as e:
        print(f"  {table}: {str(e)[:50]}...")

# Create bronze_trips as Delta table on MinIO
print("\nCreating bronze_trips (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_trips (
    event_id STRING,
    event_type STRING,
    timestamp TIMESTAMP,
    trip_id STRING,
    rider_id STRING,
    pickup_location ARRAY<DOUBLE>,
    dropoff_location ARRAY<DOUBLE>,
    pickup_zone_id STRING,
    dropoff_zone_id STRING,
    surge_multiplier DOUBLE,
    fare DOUBLE,
    driver_id STRING,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_trips/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_trips VALUES
    ('trip-001', 'trip.requested', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, NULL,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
    ('trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:05:01' AS TIMESTAMP)),
    ('trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'PIN', 'PIE', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:15:01' AS TIMESTAMP))
"""
)
print("✓ bronze_trips created")

# Create bronze_gps_pings
print("\nCreating bronze_gps_pings (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_gps_pings (
    event_id STRING,
    entity_type STRING,
    entity_id STRING,
    timestamp TIMESTAMP,
    location ARRAY<DOUBLE>,
    accuracy DOUBLE,
    heading DOUBLE,
    speed DOUBLE,
    trip_id STRING,
    trip_state STRING,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_gps_pings/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_gps_pings VALUES
    ('gps-001', 'driver', 'D001', CAST('2026-01-15 10:00:00' AS TIMESTAMP),
     ARRAY(-23.545, -46.645), 5.0, 90.0, 15.5, 'T001', 'en_route_to_pickup',
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('gps-002', 'driver', 'D001', CAST('2026-01-15 10:00:10' AS TIMESTAMP),
     ARRAY(-23.547, -46.647), 5.0, 92.0, 16.0, 'T001', 'en_route_to_pickup',
     CAST('2026-01-15 10:00:11' AS TIMESTAMP))
"""
)
print("✓ bronze_gps_pings created")

# Create bronze_driver_status
print("\nCreating bronze_driver_status (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_driver_status (
    event_id STRING,
    driver_id STRING,
    timestamp TIMESTAMP,
    new_status STRING,
    previous_status STRING,
    trigger STRING,
    location ARRAY<DOUBLE>,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_driver_status/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_driver_status VALUES
    ('status-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'idle', NULL, 'manual',
     ARRAY(-23.545, -46.645), CAST('2026-01-15 09:00:01' AS TIMESTAMP)),
    ('status-002', 'D001', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'en_route', 'idle', 'trip_matched',
     ARRAY(-23.545, -46.645), CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
    ('status-003', 'D001', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'on_trip', 'en_route', 'trip_started',
     ARRAY(-23.550, -46.650), CAST('2026-01-15 10:05:01' AS TIMESTAMP)),
    ('status-004', 'D001', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'idle', 'on_trip', 'trip_completed',
     ARRAY(-23.560, -46.660), CAST('2026-01-15 10:15:01' AS TIMESTAMP)),
    ('status-005', 'D001', CAST('2026-01-15 17:00:00' AS TIMESTAMP), 'offline', 'idle', 'manual',
     ARRAY(-23.555, -46.655), CAST('2026-01-15 17:00:01' AS TIMESTAMP))
"""
)
print("✓ bronze_driver_status created")

# Create bronze_surge_updates
print("\nCreating bronze_surge_updates (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_surge_updates (
    event_id STRING,
    zone_id STRING,
    timestamp TIMESTAMP,
    previous_multiplier DOUBLE,
    new_multiplier DOUBLE,
    available_drivers INT,
    pending_requests INT,
    calculation_window_seconds INT,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_surge_updates/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_surge_updates VALUES
    ('surge-001', 'PIN', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.2, 10, 15, 60,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('surge-002', 'PIN', CAST('2026-01-15 10:30:00' AS TIMESTAMP), 1.2, 1.5, 8, 20, 60,
     CAST('2026-01-15 10:30:01' AS TIMESTAMP)),
    ('surge-003', 'PIN', CAST('2026-01-15 10:45:00' AS TIMESTAMP), 1.5, 1.8, 6, 25, 60,
     CAST('2026-01-15 10:45:01' AS TIMESTAMP)),
    ('surge-004', 'PIE', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.0, 15, 10, 60,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP))
"""
)
print("✓ bronze_surge_updates created")

# Create bronze_payments
print("\nCreating bronze_payments (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_payments (
    event_id STRING,
    payment_id STRING,
    trip_id STRING,
    timestamp TIMESTAMP,
    rider_id STRING,
    driver_id STRING,
    payment_method_type STRING,
    payment_method_masked STRING,
    fare_amount DOUBLE,
    platform_fee_percentage DOUBLE,
    platform_fee_amount DOUBLE,
    driver_payout_amount DOUBLE,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_payments/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_payments VALUES
    ('payment-001', 'PAY001', 'T001', CAST('2026-01-15 10:16:00' AS TIMESTAMP), 'R001', 'D001',
     'credit_card', '****1234', 25.50, 25.0, 6.38, 19.12,
     CAST('2026-01-15 10:16:01' AS TIMESTAMP))
"""
)
print("✓ bronze_payments created")

# Create bronze_ratings
print("\nCreating bronze_ratings (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_ratings (
    event_id STRING,
    trip_id STRING,
    timestamp TIMESTAMP,
    rater_type STRING,
    rater_id STRING,
    ratee_type STRING,
    ratee_id STRING,
    rating DOUBLE,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_ratings/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_ratings VALUES
    ('rating-001', 'T001', CAST('2026-01-15 10:20:00' AS TIMESTAMP), 'rider', 'R001',
     'driver', 'D001', 5.0, CAST('2026-01-15 10:20:01' AS TIMESTAMP))
"""
)
print("✓ bronze_ratings created")

# Create bronze_driver_profiles (note: NOT bronze_drivers!)
print("\nCreating bronze_driver_profiles (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_driver_profiles (
    event_id STRING,
    event_type STRING,
    driver_id STRING,
    timestamp TIMESTAMP,
    first_name STRING,
    last_name STRING,
    email STRING,
    phone STRING,
    home_location ARRAY<DOUBLE>,
    preferred_zones ARRAY<STRING>,
    shift_preference STRING,
    vehicle_make STRING,
    vehicle_model STRING,
    vehicle_year INT,
    license_plate STRING,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_driver_profiles/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_driver_profiles VALUES
    ('driver-profile-001', 'driver_profile_created', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP),
     'John', 'Driver', 'john.driver@example.com', '+5511987654321',
     ARRAY(-23.545, -46.645), ARRAY('PIN', 'PIE'), 'morning',
     'Toyota', 'Corolla', 2020, 'ABC1234',
     CAST('2026-01-15 09:00:01' AS TIMESTAMP))
"""
)
print("✓ bronze_driver_profiles created")

# Create bronze_rider_profiles (note: NOT bronze_riders!)
print("\nCreating bronze_rider_profiles (Delta on MinIO)...")
cursor.execute(
    """
CREATE TABLE bronze_rider_profiles (
    event_id STRING,
    event_type STRING,
    rider_id STRING,
    timestamp TIMESTAMP,
    first_name STRING,
    last_name STRING,
    email STRING,
    phone STRING,
    home_location ARRAY<DOUBLE>,
    payment_method_type STRING,
    payment_method_masked STRING,
    behavior_factor DOUBLE,
    _ingested_at TIMESTAMP
)
USING delta
LOCATION 's3a://rideshare-bronze/bronze_rider_profiles/'
"""
)
cursor.execute(
    """
INSERT INTO bronze_rider_profiles VALUES
    ('rider-profile-001', 'rider_profile_created', 'R001', CAST('2026-01-15 08:00:00' AS TIMESTAMP),
     'Jane', 'Rider', 'jane.rider@example.com', '+5511912345678',
     ARRAY(-23.550, -46.650), 'credit_card', '****1234', 0.8,
     CAST('2026-01-15 08:00:01' AS TIMESTAMP))
"""
)
print("✓ bronze_rider_profiles created")

# Verify row counts
print("\nVerifying row counts:")
for table in [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_payments",
    "bronze_ratings",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")

# Verify data is on MinIO
print("\nVerifying table locations:")
for table in ["bronze_trips", "bronze_driver_profiles"]:
    cursor.execute(f"DESCRIBE EXTENDED {table}")
    rows = cursor.fetchall()
    for row in rows:
        if row[0] and "Location" in str(row[0]):
            print(f"  {table}: {row[1]}")
            break

cursor.close()
conn.close()

print("\n✓ All Bronze Delta tables created on MinIO successfully!")
