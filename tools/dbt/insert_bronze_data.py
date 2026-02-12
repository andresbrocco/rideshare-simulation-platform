#!/usr/bin/env python3
"""Insert data into existing Bronze tables"""

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

print("Inserting data into Bronze tables...")

# Insert into bronze_trips
print("Inserting into bronze_trips...")
cursor.execute(
    """
INSERT INTO bronze_trips
VALUES
    ('trip-001', 'trip.requested', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, NULL,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
    ('trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:05:01' AS TIMESTAMP)),
    ('trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(-23.550, -46.650), ARRAY(-23.560, -46.660), 'Z01', 'Z02', 1.2, 25.50, 'D001',
     CAST('2026-01-15 10:15:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 4 rows into bronze_trips")

# Insert into bronze_gps_pings
print("Inserting into bronze_gps_pings...")
cursor.execute(
    """
INSERT INTO bronze_gps_pings
VALUES
    ('gps-001', 'driver', 'D001', CAST('2026-01-15 10:00:00' AS TIMESTAMP),
     ARRAY(-23.545, -46.645), 5.0, 90.0, 15.5, 'T001', 'en_route_to_pickup',
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('gps-002', 'driver', 'D001', CAST('2026-01-15 10:00:10' AS TIMESTAMP),
     ARRAY(-23.547, -46.647), 5.0, 92.0, 16.0, 'T001', 'en_route_to_pickup',
     CAST('2026-01-15 10:00:11' AS TIMESTAMP)),
    ('gps-003', 'rider', 'R001', CAST('2026-01-15 10:00:00' AS TIMESTAMP),
     ARRAY(-23.550, -46.650), 3.0, NULL, NULL, NULL, NULL,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 3 rows into bronze_gps_pings")

# Insert into bronze_driver_status
print("Inserting into bronze_driver_status...")
cursor.execute(
    """
INSERT INTO bronze_driver_status
VALUES
    ('status-001', 'D001', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'idle', NULL, 'manual',
     ARRAY(-23.545, -46.645), CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('status-002', 'D001', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'dispatched', 'idle', 'trip_matched',
     ARRAY(-23.545, -46.645), CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
    ('status-003', 'D001', CAST('2026-01-15 10:00:30' AS TIMESTAMP), 'en_route_to_pickup', 'dispatched', 'trip_accepted',
     ARRAY(-23.547, -46.647), CAST('2026-01-15 10:00:31' AS TIMESTAMP))
"""
)
print("✓ Inserted 3 rows into bronze_driver_status")

# Insert into bronze_surge_updates
print("Inserting into bronze_surge_updates...")
cursor.execute(
    """
INSERT INTO bronze_surge_updates
VALUES
    ('surge-001', 'Z01', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.2, 10, 15, 60,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('surge-002', 'Z01', CAST('2026-01-15 10:01:00' AS TIMESTAMP), 1.2, 1.5, 8, 20, 60,
     CAST('2026-01-15 10:01:01' AS TIMESTAMP)),
    ('surge-003', 'Z02', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 1.0, 1.0, 15, 10, 60,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 3 rows into bronze_surge_updates")

# Commit the transaction
print("\nCommitting transaction...")
conn.commit()

# Verify row counts
print("\nVerifying row counts:")
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
