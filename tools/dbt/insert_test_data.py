#!/usr/bin/env python3
"""Insert test data into Bronze tables"""

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

print("Inserting test data into Bronze tables...")

# Insert into bronze_trips
print("\nInserting into bronze_trips...")
cursor.execute(
    """
INSERT INTO bronze_trips VALUES
    ('trip-001', 'trip.requested', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), NULL,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_trips VALUES
    ('trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:00:06' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_trips VALUES
    ('trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:05:01' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_trips VALUES
    ('trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:15:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 4 rows into bronze_trips")

# Insert into bronze_driver_status
print("\nInserting into bronze_driver_status...")
cursor.execute(
    """
INSERT INTO bronze_driver_status VALUES
    ('status-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'online', NULL, 'manual',
     ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
     CAST('2026-01-15 09:00:01' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_driver_status VALUES
    ('status-002', 'D001', CAST('2026-01-15 17:00:00' AS TIMESTAMP), 'offline', 'online', 'manual',
     ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
     CAST('2026-01-15 17:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 2 rows into bronze_driver_status")

# Insert into bronze_surge_updates
print("\nInserting into bronze_surge_updates...")
cursor.execute(
    """
INSERT INTO bronze_surge_updates VALUES
    ('surge-001', 'PIN', CAST('2026-01-15 10:00:00' AS TIMESTAMP), CAST(1.0 AS DECIMAL(2,1)),
     CAST(1.2 AS DECIMAL(2,1)), 10, 15, 60, CAST('2026-01-15 10:00:01' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_surge_updates VALUES
    ('surge-002', 'PIN', CAST('2026-01-15 10:30:00' AS TIMESTAMP), CAST(1.2 AS DECIMAL(2,1)),
     CAST(1.5 AS DECIMAL(2,1)), 8, 20, 60, CAST('2026-01-15 10:30:01' AS TIMESTAMP))
"""
)
cursor.execute(
    """
INSERT INTO bronze_surge_updates VALUES
    ('surge-003', 'PIN', CAST('2026-01-15 10:45:00' AS TIMESTAMP), CAST(1.5 AS DECIMAL(2,1)),
     CAST(1.8 AS DECIMAL(2,1)), 6, 25, 60, CAST('2026-01-15 10:45:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 3 rows into bronze_surge_updates")

# Insert into bronze_payments
print("\nInserting into bronze_payments...")
cursor.execute(
    """
INSERT INTO bronze_payments VALUES
    ('payment-001', 'PAY001', 'T001', CAST('2026-01-15 10:16:00' AS TIMESTAMP), 'R001', 'D001',
     'credit_card', '****1234', CAST(25.50 AS DECIMAL(4,2)), CAST(25.0 AS DECIMAL(3,1)),
     CAST(6.38 AS DECIMAL(3,2)), CAST(19.12 AS DECIMAL(4,2)), CAST('2026-01-15 10:16:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 1 row into bronze_payments")

# Insert into bronze_ratings
print("\nInserting into bronze_ratings...")
cursor.execute(
    """
INSERT INTO bronze_ratings VALUES
    ('rating-001', 'T001', CAST('2026-01-15 10:20:00' AS TIMESTAMP), 'rider', 'R001', 'driver', 'D001',
     CAST(5.0 AS DECIMAL(2,1)), CAST('2026-01-15 10:20:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 1 row into bronze_ratings")

# Insert into bronze_drivers
print("\nInserting into bronze_drivers...")
cursor.execute(
    """
INSERT INTO bronze_drivers VALUES
    ('driver-profile-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'update', 'John Driver',
     'john.driver@example.com', '+5511987654321', 'Toyota', 'Corolla', 2020, 'ABC1234', 'White',
     CAST('2026-01-15 09:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 1 row into bronze_drivers")

# Insert into bronze_riders
print("\nInserting into bronze_riders...")
cursor.execute(
    """
INSERT INTO bronze_riders VALUES
    ('rider-profile-001', 'R001', CAST('2026-01-15 08:00:00' AS TIMESTAMP), 'update', 'Jane Rider',
     'jane.rider@example.com', '+5511912345678', CAST('2026-01-15 08:00:01' AS TIMESTAMP))
"""
)
print("✓ Inserted 1 row into bronze_riders")

# Verify row counts
# Commit the transaction
print("\nCommitting transaction...")
conn.commit()

print("\nVerifying row counts:")
for table in [
    "bronze_trips",
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

print("\n✓ All test data inserted successfully!")
