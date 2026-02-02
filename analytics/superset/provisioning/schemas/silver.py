"""Silver layer table definitions.

Silver tables contain cleaned, validated, and enriched data.
Includes staging tables and anomaly detection tables.
"""

# Silver layer staging tables
SILVER_STAGING_TABLES: tuple[str, ...] = (
    "silver.stg_trips",
    "silver.stg_gps_pings",
    "silver.stg_driver_status",
    "silver.stg_surge_updates",
    "silver.stg_ratings",
    "silver.stg_payments",
    "silver.stg_drivers",
    "silver.stg_riders",
)

# Silver layer anomaly tables
SILVER_ANOMALY_TABLES: tuple[str, ...] = (
    "silver.anomalies_gps_outliers",
    "silver.anomalies_impossible_speeds",
    "silver.anomalies_zombie_drivers",
    "silver.anomalies_all",
)

# All Silver tables
SILVER_TABLES: tuple[str, ...] = SILVER_STAGING_TABLES + SILVER_ANOMALY_TABLES
