#!/usr/bin/env python3
"""Populate Bronze tables using Spark DataFrame API"""

from pyspark.sql import SparkSession
from datetime import datetime
from decimal import Decimal

# Create Spark session
spark = (
    SparkSession.builder.appName("PopulateBronzeTables")
    .config("spark.sql.catalogImplementation", "hive")
    .enableHiveSupport()
    .getOrCreate()
)

spark.sql("USE default")

# bronze_drivers
print("Inserting into bronze_drivers...")
drivers_data = [
    (
        "driver-profile-001",
        "D001",
        datetime(2026, 1, 15, 8, 0, 0),
        "driver.profile_created",
        "John Driver",
        "john.driver@example.com",
        "+5511987654321",
        "Toyota",
        "Corolla",
        2020,
        "ABC1234",
        "White",
        datetime(2026, 1, 15, 8, 0, 1),
    )
]
spark.createDataFrame(
    drivers_data,
    [
        "event_id",
        "driver_id",
        "timestamp",
        "event_type",
        "name",
        "email",
        "phone",
        "vehicle_make",
        "vehicle_model",
        "vehicle_year",
        "vehicle_plate",
        "vehicle_color",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_drivers")
print("✓ bronze_drivers populated")

# bronze_riders
print("Inserting into bronze_riders...")
riders_data = [
    (
        "rider-profile-001",
        "R001",
        datetime(2026, 1, 15, 7, 0, 0),
        "rider.profile_created",
        "Jane Rider",
        "jane.rider@example.com",
        "+5511912345678",
        datetime(2026, 1, 15, 7, 0, 1),
    )
]
spark.createDataFrame(
    riders_data,
    [
        "event_id",
        "rider_id",
        "timestamp",
        "event_type",
        "name",
        "email",
        "phone",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_riders")
print("✓ bronze_riders populated")

# bronze_trips
print("Inserting into bronze_trips...")
trips_data = [
    (
        "trip-001",
        "trip.requested",
        datetime(2026, 1, 15, 10, 0, 0),
        "T001",
        "R001",
        [Decimal("-23.550"), Decimal("-46.650")],
        [Decimal("-23.560"), Decimal("-46.660")],
        "PIN",
        "PIE",
        Decimal("1.2"),
        Decimal("25.50"),
        None,
        datetime(2026, 1, 15, 10, 0, 1),
    ),
    (
        "trip-002",
        "trip.matched",
        datetime(2026, 1, 15, 10, 0, 5),
        "T001",
        "R001",
        [Decimal("-23.550"), Decimal("-46.650")],
        [Decimal("-23.560"), Decimal("-46.660")],
        "PIN",
        "PIE",
        Decimal("1.2"),
        Decimal("25.50"),
        "D001",
        datetime(2026, 1, 15, 10, 0, 6),
    ),
    (
        "trip-003",
        "trip.started",
        datetime(2026, 1, 15, 10, 5, 0),
        "T001",
        "R001",
        [Decimal("-23.550"), Decimal("-46.650")],
        [Decimal("-23.560"), Decimal("-46.660")],
        "PIN",
        "PIE",
        Decimal("1.2"),
        Decimal("25.50"),
        "D001",
        datetime(2026, 1, 15, 10, 5, 1),
    ),
    (
        "trip-004",
        "trip.completed",
        datetime(2026, 1, 15, 10, 15, 0),
        "T001",
        "R001",
        [Decimal("-23.550"), Decimal("-46.650")],
        [Decimal("-23.560"), Decimal("-46.660")],
        "PIN",
        "PIE",
        Decimal("1.2"),
        Decimal("25.50"),
        "D001",
        datetime(2026, 1, 15, 10, 15, 1),
    ),
]
spark.createDataFrame(
    trips_data,
    [
        "event_id",
        "event_type",
        "timestamp",
        "trip_id",
        "rider_id",
        "pickup_location",
        "dropoff_location",
        "pickup_zone_id",
        "dropoff_zone_id",
        "surge_multiplier",
        "fare",
        "driver_id",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_trips")
print("✓ bronze_trips populated")

# bronze_gps_pings
print("Inserting into bronze_gps_pings...")
gps_data = [
    (
        "gps-001",
        "driver",
        "D001",
        datetime(2026, 1, 15, 10, 1, 0),
        [Decimal("-23.550"), Decimal("-46.650")],
        Decimal("10.0"),
        Decimal("45.0"),
        Decimal("5.0"),
        "T001",
        "matched",
        datetime(2026, 1, 15, 10, 1, 1),
    ),
    (
        "gps-002",
        "rider",
        "R001",
        datetime(2026, 1, 15, 10, 1, 0),
        [Decimal("-23.550"), Decimal("-46.650")],
        Decimal("10.0"),
        Decimal("0.0"),
        Decimal("0.0"),
        "T001",
        "matched",
        datetime(2026, 1, 15, 10, 1, 1),
    ),
]
spark.createDataFrame(
    gps_data,
    [
        "event_id",
        "entity_type",
        "entity_id",
        "timestamp",
        "location",
        "accuracy",
        "heading",
        "speed",
        "trip_id",
        "trip_state",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_gps_pings")
print("✓ bronze_gps_pings populated")

# bronze_driver_status
print("Inserting into bronze_driver_status...")
status_data = [
    (
        "status-001",
        "D001",
        datetime(2026, 1, 15, 9, 0, 0),
        "idle",
        None,
        "manual",
        [Decimal("-23.545"), Decimal("-46.645")],
        datetime(2026, 1, 15, 9, 0, 1),
    ),
    (
        "status-002",
        "D001",
        datetime(2026, 1, 15, 17, 0, 0),
        "offline",
        "idle",
        "manual",
        [Decimal("-23.545"), Decimal("-46.645")],
        datetime(2026, 1, 15, 17, 0, 1),
    ),
]
spark.createDataFrame(
    status_data,
    [
        "event_id",
        "driver_id",
        "timestamp",
        "new_status",
        "previous_status",
        "trigger",
        "location",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_driver_status")
print("✓ bronze_driver_status populated")

# bronze_surge_updates
print("Inserting into bronze_surge_updates...")
surge_data = [
    (
        "surge-001",
        "PIN",
        datetime(2026, 1, 15, 10, 0, 0),
        Decimal("1.0"),
        Decimal("1.2"),
        10,
        15,
        60,
        datetime(2026, 1, 15, 10, 0, 1),
    ),
    (
        "surge-002",
        "PIN",
        datetime(2026, 1, 15, 10, 30, 0),
        Decimal("1.2"),
        Decimal("1.5"),
        8,
        20,
        60,
        datetime(2026, 1, 15, 10, 30, 1),
    ),
    (
        "surge-003",
        "PIN",
        datetime(2026, 1, 15, 10, 45, 0),
        Decimal("1.5"),
        Decimal("1.8"),
        6,
        25,
        60,
        datetime(2026, 1, 15, 10, 45, 1),
    ),
]
spark.createDataFrame(
    surge_data,
    [
        "event_id",
        "zone_id",
        "timestamp",
        "previous_multiplier",
        "new_multiplier",
        "available_drivers",
        "pending_requests",
        "calculation_window_seconds",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_surge_updates")
print("✓ bronze_surge_updates populated")

# bronze_payments
print("Inserting into bronze_payments...")
payments_data = [
    (
        "payment-001",
        "PAY001",
        "T001",
        datetime(2026, 1, 15, 10, 16, 0),
        "R001",
        "D001",
        "credit_card",
        "****1234",
        Decimal("25.50"),
        Decimal("25.0"),
        Decimal("6.38"),
        Decimal("19.12"),
        datetime(2026, 1, 15, 10, 16, 1),
    )
]
spark.createDataFrame(
    payments_data,
    [
        "event_id",
        "payment_id",
        "trip_id",
        "timestamp",
        "rider_id",
        "driver_id",
        "payment_method_type",
        "payment_method_masked",
        "fare_amount",
        "platform_fee_percentage",
        "platform_fee_amount",
        "driver_payout_amount",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_payments")
print("✓ bronze_payments populated")

# bronze_ratings
print("Inserting into bronze_ratings...")
ratings_data = [
    (
        "rating-001",
        "T001",
        datetime(2026, 1, 15, 10, 20, 0),
        "rider",
        "R001",
        "driver",
        "D001",
        Decimal("5.0"),
        datetime(2026, 1, 15, 10, 20, 1),
    )
]
spark.createDataFrame(
    ratings_data,
    [
        "event_id",
        "trip_id",
        "timestamp",
        "rater_type",
        "rater_id",
        "ratee_type",
        "ratee_id",
        "rating",
        "_ingested_at",
    ],
).write.mode("append").saveAsTable("bronze_ratings")
print("✓ bronze_ratings populated")

# Verify counts
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
    count = spark.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    print(f"  {table}: {count} rows")

spark.stop()
print("\n✓ All Bronze tables populated successfully!")
