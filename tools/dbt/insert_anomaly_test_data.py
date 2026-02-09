#!/usr/bin/env python3
"""Insert test data for anomaly detection tests"""

from pyhive import hive

conn = hive.Connection(host="localhost", port=10000, database="default")
cursor = conn.cursor()

print("Inserting test data for anomaly detection...")

# Insert zombie driver test data
print("\n1. Inserting zombie driver test data...")
cursor.execute(
    """
INSERT INTO bronze_driver_status
VALUES
    ('evt_status_001', 'driver_001', CAST('2026-01-16 10:00:00' AS TIMESTAMP), 'idle', 'offline', 'went_online',
     ARRAY(-23.5, -46.6), CAST('2026-01-16 10:00:01' AS TIMESTAMP)),
    ('evt_status_002', 'driver_002', CAST('2026-01-16 10:00:00' AS TIMESTAMP), 'idle', 'offline', 'went_online',
     ARRAY(-23.6, -46.7), CAST('2026-01-16 10:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted driver status records")

cursor.execute(
    """
INSERT INTO bronze_gps_pings
VALUES
    ('evt_gps_001', 'driver', 'driver_001', CAST('2026-01-16 10:05:00' AS TIMESTAMP),
     ARRAY(-23.5, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 10:05:01' AS TIMESTAMP)),
    ('evt_gps_002', 'driver', 'driver_002', CAST('2026-01-16 10:15:00' AS TIMESTAMP),
     ARRAY(-23.6, -46.7), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 10:15:01' AS TIMESTAMP))
"""
)
print("✓ Inserted GPS ping records for zombie driver test")

# Insert GPS outlier test data
print("\n2. Inserting GPS outlier test data...")
cursor.execute(
    """
INSERT INTO bronze_gps_pings
VALUES
    ('evt_gps_outlier_001', 'driver', 'driver_003', CAST('2026-01-16 11:00:00' AS TIMESTAMP),
     ARRAY(-22.0, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 11:00:01' AS TIMESTAMP)),
    ('evt_gps_valid_001', 'driver', 'driver_004', CAST('2026-01-16 11:00:00' AS TIMESTAMP),
     ARRAY(-23.5, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 11:00:01' AS TIMESTAMP)),
    ('evt_gps_outlier_002', 'driver', 'driver_005', CAST('2026-01-16 11:01:00' AS TIMESTAMP),
     ARRAY(-23.5, -50.0), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 11:01:01' AS TIMESTAMP)),
    ('evt_gps_outlier_003', 'driver', 'driver_006', CAST('2026-01-16 11:02:00' AS TIMESTAMP),
     ARRAY(-24.0, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 11:02:01' AS TIMESTAMP))
"""
)
print("✓ Inserted GPS outlier test records")

# Insert impossible speed test data
print("\n3. Inserting impossible speed test data...")
cursor.execute(
    """
INSERT INTO bronze_gps_pings
VALUES
    ('evt_speed_001', 'driver', 'driver_007', CAST('2026-01-16 12:00:00' AS TIMESTAMP),
     ARRAY(-23.5, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 12:00:01' AS TIMESTAMP)),
    ('evt_speed_002', 'driver', 'driver_007', CAST('2026-01-16 12:02:00' AS TIMESTAMP),
     ARRAY(-23.3, -46.4), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 12:02:01' AS TIMESTAMP)),
    ('evt_speed_003', 'driver', 'driver_008', CAST('2026-01-16 12:00:00' AS TIMESTAMP),
     ARRAY(-23.5, -46.6), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 12:00:01' AS TIMESTAMP)),
    ('evt_speed_004', 'driver', 'driver_008', CAST('2026-01-16 12:10:00' AS TIMESTAMP),
     ARRAY(-23.51, -46.61), 5.0, 90.0, 5.0, NULL, NULL, CAST('2026-01-16 12:10:01' AS TIMESTAMP))
"""
)
print("✓ Inserted impossible speed test records")

print("\n✓ All test data inserted successfully!")

cursor.close()
conn.close()
