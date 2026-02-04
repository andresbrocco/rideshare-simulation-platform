"""Silver layer dataset definitions for Superset provisioning.

These datasets query the Silver layer tables for Data Quality Monitoring dashboard
and some Platform Operations datasets.
"""

from provisioning.dashboards.base import DatasetDefinition


# =============================================================================
# Data Quality Monitoring - KPI Datasets
# =============================================================================

DQ_TOTAL_ANOMALIES = DatasetDefinition(
    name="dq_total_anomalies",
    description="Total count of all anomalies detected in the last 24 hours across all anomaly types",
    sql="""
SELECT COUNT(*) as total_anomalies
FROM silver.anomalies_all
WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
""",
)

DQ_GPS_OUTLIER_COUNT = DatasetDefinition(
    name="dq_gps_outlier_count",
    description="Count of GPS coordinates outside Sao Paulo bounds (lat: -23.8 to -23.3, lon: -46.9 to -46.3)",
    sql="""
SELECT COUNT(*) as gps_outliers
FROM silver.anomalies_gps_outliers
WHERE timestamp >= current_timestamp - INTERVAL 24 HOURS
""",
)

DQ_IMPOSSIBLE_SPEED_COUNT = DatasetDefinition(
    name="dq_impossible_speed_count",
    description="Count of calculated speeds exceeding 200 km/h indicating timestamp or location errors",
    sql="""
SELECT COUNT(*) as impossible_speeds
FROM silver.anomalies_impossible_speeds
WHERE timestamp >= current_timestamp - INTERVAL 24 HOURS
""",
)


# =============================================================================
# Data Quality Monitoring - Anomaly Analysis Datasets
# =============================================================================

DQ_ANOMALIES_BY_CATEGORY = DatasetDefinition(
    name="dq_anomalies_by_category",
    description="Breakdown of anomaly types (gps_outlier, impossible_speed, zombie_driver) for proportional analysis",
    sql="""
SELECT
    anomaly_type,
    COUNT(*) as count
FROM silver.anomalies_all
WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
GROUP BY anomaly_type
ORDER BY count DESC
""",
)

DQ_ANOMALIES_TREND = DatasetDefinition(
    name="dq_anomalies_trend",
    description="Hourly time series of anomalies by type to identify spikes and degradation patterns",
    sql="""
SELECT
    date_trunc('hour', detected_at) as hour,
    anomaly_type,
    COUNT(*) as count
FROM silver.anomalies_all
WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
GROUP BY date_trunc('hour', detected_at), anomaly_type
ORDER BY hour
""",
)


# =============================================================================
# Data Quality Monitoring - Stale Driver Dataset
# =============================================================================

DQ_STALE_DRIVERS = DatasetDefinition(
    name="dq_stale_drivers",
    description="Drivers marked as active but not sending GPS updates for 10+ minutes, requires investigation",
    sql="""
SELECT
    driver_id,
    current_status,
    last_gps_timestamp,
    last_status_timestamp,
    ROUND(minutes_since_last_ping, 1) as minutes_stale
FROM silver.anomalies_zombie_drivers
WHERE last_status_timestamp >= current_timestamp - INTERVAL 24 HOURS
ORDER BY minutes_since_last_ping DESC
LIMIT 50
""",
)


# =============================================================================
# Data Quality Monitoring - Table Health Datasets
# =============================================================================

DQ_STAGING_ROW_COUNTS = DatasetDefinition(
    name="dq_staging_row_counts",
    description="Row counts for all Silver staging tables to verify data flow through pipeline",
    sql="""
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
) counts
ORDER BY row_count DESC
""",
)

DQ_STAGING_FRESHNESS = DatasetDefinition(
    name="dq_staging_freshness",
    description="Most recent event timestamp per staging table to detect stale/failed pipeline stages",
    sql="""
SELECT table_name, latest_event, minutes_since_update
FROM (
    SELECT
        'stg_trips' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_trips
    UNION ALL
    SELECT
        'stg_gps_pings' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_gps_pings
    UNION ALL
    SELECT
        'stg_driver_status' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_driver_status
    UNION ALL
    SELECT
        'stg_surge_updates' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_surge_updates
    UNION ALL
    SELECT
        'stg_ratings' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_ratings
    UNION ALL
    SELECT
        'stg_payments' as table_name,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_payments
) freshness
ORDER BY minutes_since_update ASC
""",
)


# =============================================================================
# Platform Operations - Silver Layer Datasets (anomalies, active trips)
# =============================================================================

OPS_ACTIVE_TRIPS = DatasetDefinition(
    name="ops_active_trips",
    description="Active trips currently in progress (driver en route or rider in vehicle). Uses Silver layer stg_trips to find non-terminal trip states.",
    sql="""
WITH latest_trip_states AS (
  SELECT
    trip_id,
    trip_state,
    timestamp,
    ROW_NUMBER() OVER (PARTITION BY trip_id ORDER BY timestamp DESC) AS rn
  FROM silver.stg_trips
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
),
current_states AS (
  SELECT trip_id, trip_state
  FROM latest_trip_states
  WHERE rn = 1
)
SELECT
  COUNT(*) AS active_trips
FROM current_states
WHERE trip_state IN ('driver_en_route', 'driver_arrived', 'started')
""",
)

OPS_RECENT_ERRORS = DatasetDefinition(
    name="ops_recent_errors",
    description="Count of processing anomalies/errors detected in the last hour.",
    sql="""
SELECT
  COUNT(*) AS error_count_last_hour
FROM silver.anomalies_all
WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR
""",
)

OPS_ERRORS_BY_CATEGORY = DatasetDefinition(
    name="ops_errors_by_category",
    description="Breakdown of anomalies by type for the last 24 hours.",
    sql="""
SELECT
  anomaly_type,
  COUNT(*) AS error_count
FROM silver.anomalies_all
WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
GROUP BY anomaly_type
ORDER BY error_count DESC
""",
)


# =============================================================================
# All Silver Datasets
# =============================================================================

SILVER_DATASETS: tuple[DatasetDefinition, ...] = (
    # Data Quality Monitoring
    DQ_TOTAL_ANOMALIES,
    DQ_GPS_OUTLIER_COUNT,
    DQ_IMPOSSIBLE_SPEED_COUNT,
    DQ_ANOMALIES_BY_CATEGORY,
    DQ_ANOMALIES_TREND,
    DQ_STALE_DRIVERS,
    DQ_STAGING_ROW_COUNTS,
    DQ_STAGING_FRESHNESS,
    # Platform Operations (Silver)
    OPS_ACTIVE_TRIPS,
    OPS_RECENT_ERRORS,
    OPS_ERRORS_BY_CATEGORY,
)
