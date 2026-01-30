"""
Centralized SQL query library for Silver Quality Dashboard.

All queries use Spark SQL syntax and reference Silver layer tables.
Tables are in the 'silver' schema with naming convention:
- Staging tables: stg_* (stg_trips, stg_gps_pings, stg_driver_status, stg_surge_updates,
                         stg_ratings, stg_payments, stg_drivers, stg_riders)
- Anomaly tables: anomalies_* (anomalies_all, anomalies_gps_outliers,
                               anomalies_impossible_speeds, anomalies_zombie_drivers)

Silver layer performs:
- JSON parsing from Bronze raw values
- Deduplication on event_id
- Data quality checks and anomaly detection
"""

# =============================================================================
# SILVER QUALITY DASHBOARD QUERIES (8 queries)
# =============================================================================

# Total anomalies detected (last 24 hours)
TOTAL_ANOMALIES = """
SELECT COUNT(*) as count
FROM silver.anomalies_all
WHERE detected_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
"""

# Anomaly type distribution
ANOMALIES_BY_TYPE = """
SELECT
    anomaly_type,
    COUNT(*) as count
FROM silver.anomalies_all
WHERE detected_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
GROUP BY anomaly_type
ORDER BY count DESC
"""

# Anomalies per hour (time series, last 24 hours)
ANOMALIES_OVER_TIME = """
SELECT
    DATE_TRUNC('hour', detected_at) as hour,
    COUNT(*) as anomaly_count
FROM silver.anomalies_all
WHERE detected_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
GROUP BY DATE_TRUNC('hour', detected_at)
ORDER BY hour
"""

# GPS outliers count (boundary violations: lat not in [-23.8, -23.3], lon not in [-46.9, -46.3])
GPS_OUTLIERS_COUNT = """
SELECT COUNT(*) as count
FROM silver.anomalies_gps_outliers
WHERE timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
"""

# Impossible speeds count (speeds > 200 km/h)
IMPOSSIBLE_SPEEDS_COUNT = """
SELECT COUNT(*) as count
FROM silver.anomalies_impossible_speeds
WHERE timestamp >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
"""

# Zombie drivers list (active drivers with no GPS for 10+ minutes)
ZOMBIE_DRIVERS_LIST = """
SELECT
    driver_id,
    current_status,
    last_gps_timestamp,
    last_status_timestamp,
    ROUND(minutes_since_last_ping, 1) as minutes_since_last_ping
FROM silver.anomalies_zombie_drivers
ORDER BY minutes_since_last_ping DESC
LIMIT 20
"""

# Row counts per staging table
STAGING_ROW_COUNTS = """
SELECT table_name, row_count
FROM (
    SELECT 'stg_trips' as table_name, COUNT(*) as row_count FROM silver.stg_trips
    UNION ALL
    SELECT 'stg_gps_pings' as table_name, COUNT(*) as row_count FROM silver.stg_gps_pings
    UNION ALL
    SELECT 'stg_driver_status' as table_name, COUNT(*) as row_count FROM silver.stg_driver_status
    UNION ALL
    SELECT 'stg_surge_updates' as table_name, COUNT(*) as row_count FROM silver.stg_surge_updates
    UNION ALL
    SELECT 'stg_ratings' as table_name, COUNT(*) as row_count FROM silver.stg_ratings
    UNION ALL
    SELECT 'stg_payments' as table_name, COUNT(*) as row_count FROM silver.stg_payments
    UNION ALL
    SELECT 'stg_drivers' as table_name, COUNT(*) as row_count FROM silver.stg_drivers
    UNION ALL
    SELECT 'stg_riders' as table_name, COUNT(*) as row_count FROM silver.stg_riders
) table_counts
ORDER BY row_count DESC
"""

# Data freshness per staging table (latest _ingested_at timestamp)
STAGING_FRESHNESS = """
SELECT table_name, latest_timestamp
FROM (
    SELECT 'stg_trips' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_trips
    UNION ALL
    SELECT 'stg_gps_pings' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_gps_pings
    UNION ALL
    SELECT 'stg_driver_status' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_driver_status
    UNION ALL
    SELECT 'stg_surge_updates' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_surge_updates
    UNION ALL
    SELECT 'stg_ratings' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_ratings
    UNION ALL
    SELECT 'stg_payments' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_payments
    UNION ALL
    SELECT 'stg_drivers' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_drivers
    UNION ALL
    SELECT 'stg_riders' as table_name, MAX(_ingested_at) as latest_timestamp FROM silver.stg_riders
) table_freshness
ORDER BY latest_timestamp DESC
"""


# =============================================================================
# QUERY COLLECTION
# =============================================================================

SILVER_QUALITY_QUERIES = {
    "total_anomalies": TOTAL_ANOMALIES,
    "anomalies_by_type": ANOMALIES_BY_TYPE,
    "anomalies_over_time": ANOMALIES_OVER_TIME,
    "gps_outliers_count": GPS_OUTLIERS_COUNT,
    "impossible_speeds_count": IMPOSSIBLE_SPEEDS_COUNT,
    "zombie_drivers_list": ZOMBIE_DRIVERS_LIST,
    "staging_row_counts": STAGING_ROW_COUNTS,
    "staging_freshness": STAGING_FRESHNESS,
}
