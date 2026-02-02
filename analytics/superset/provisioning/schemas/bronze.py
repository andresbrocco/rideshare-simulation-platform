"""Bronze layer table definitions.

Bronze tables store raw data from Kafka topics with minimal transformation.
"""

# Bronze layer table names
BRONZE_TABLES: tuple[str, ...] = (
    "bronze.bronze_trips",
    "bronze.bronze_gps_pings",
    "bronze.bronze_driver_status",
    "bronze.bronze_surge_updates",
    "bronze.bronze_ratings",
    "bronze.bronze_payments",
    "bronze.bronze_driver_profiles",
    "bronze.bronze_rider_profiles",
    "bronze.bronze_dlq",  # Dead letter queue
)
