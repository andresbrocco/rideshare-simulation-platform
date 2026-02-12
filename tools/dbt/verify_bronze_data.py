#!/usr/bin/env python3
"""Verify Bronze tables have data"""

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

print("Checking Bronze tables...")
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

    if count == 0:
        cursor.execute(f"DESCRIBE {table}")
        print(f"    Schema: {cursor.fetchall()}")

cursor.close()
conn.close()
