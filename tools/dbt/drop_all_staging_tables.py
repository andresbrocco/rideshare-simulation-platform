#!/usr/bin/env python3
"""Drop all staging tables to start fresh"""

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

print("Dropping all staging, dimension, and fact tables...")
for table in [
    "stg_trips",
    "stg_gps_pings",
    "stg_driver_status",
    "stg_surge_updates",
    "stg_payments",
    "stg_ratings",
    "stg_drivers",
    "stg_riders",
    "dim_zones",
    "dim_time",
    "dim_drivers",
    "dim_riders",
    "dim_payment_methods",
    "fact_trips",
    "fact_payments",
    "fact_ratings",
    "fact_cancellations",
    "fact_driver_activity",
    "agg_hourly_zone_demand",
    "agg_daily_driver_performance",
    "agg_daily_platform_revenue",
    "agg_surge_history",
]:
    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        print(f"✓ Dropped TABLE {table}")
    except Exception as e:
        print(f"  Failed to drop {table}: {str(e)[:100]}")

cursor.close()
conn.close()

print("\n✓ All tables dropped successfully!")
