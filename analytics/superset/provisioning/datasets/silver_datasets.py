"""Silver layer dataset definitions for Superset provisioning.

These datasets query the Silver layer tables for Data Quality Monitoring dashboard
and some Platform Operations datasets.
"""

from provisioning.dashboards.base import (
    ColumnDefinition,
    DatasetDefinition,
    MetricDefinition,
)


# =============================================================================
# Silver Layer - CONSOLIDATED DATASETS
# =============================================================================

# Consolidated anomalies dataset - replaces 5 single-purpose anomaly datasets
SILVER_ANOMALIES = DatasetDefinition(
    name="silver_anomalies",
    description="All detected anomalies with type and timestamp - consolidated for data quality charts",
    sql="""
SELECT
    detected_at,
    DATE_TRUNC('hour', detected_at) AS hour_timestamp,
    anomaly_type,
    entity_type,
    entity_id,
    severity,
    details
FROM silver.anomalies_all
""",
    columns=(
        ColumnDefinition(
            "detected_at",
            "TIMESTAMP",
            "Detected At",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "anomaly_type",
            "VARCHAR",
            "Anomaly Type",
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "entity_type",
            "VARCHAR",
            "Entity Type",
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("entity_id", "VARCHAR", "Entity ID", filterable=True, groupby=True),
        ColumnDefinition("severity", "VARCHAR", "Severity", filterable=True, groupby=True),
        ColumnDefinition("details", "VARCHAR", "Details", filterable=False, groupby=False),
    ),
    metrics=(
        MetricDefinition(
            "count_anomalies",
            "COUNT(*)",
            "Anomaly Count",
            d3format=",d",
        ),
        MetricDefinition(
            "count_distinct_entities",
            "COUNT(DISTINCT entity_id)",
            "Affected Entities",
            d3format=",d",
        ),
    ),
    main_dttm_col="detected_at",
    cache_timeout=60,
)


# Consolidated staging health dataset - replaces row counts + freshness datasets
SILVER_STAGING_HEALTH = DatasetDefinition(
    name="silver_staging_health",
    description="Silver staging table health metrics (row counts and freshness)",
    sql="""
SELECT
    table_name,
    row_count,
    latest_event,
    minutes_since_update
FROM (
    SELECT
        'stg_trips' as table_name,
        (SELECT COUNT(*) FROM silver.stg_trips) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_trips
    UNION ALL
    SELECT
        'stg_gps_pings' as table_name,
        (SELECT COUNT(*) FROM silver.stg_gps_pings) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_gps_pings
    UNION ALL
    SELECT
        'stg_driver_status' as table_name,
        (SELECT COUNT(*) FROM silver.stg_driver_status) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_driver_status
    UNION ALL
    SELECT
        'stg_surge_updates' as table_name,
        (SELECT COUNT(*) FROM silver.stg_surge_updates) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_surge_updates
    UNION ALL
    SELECT
        'stg_ratings' as table_name,
        (SELECT COUNT(*) FROM silver.stg_ratings) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_ratings
    UNION ALL
    SELECT
        'stg_payments' as table_name,
        (SELECT COUNT(*) FROM silver.stg_payments) as row_count,
        MAX(timestamp) as latest_event,
        ROUND((unix_timestamp(current_timestamp) - unix_timestamp(MAX(timestamp))) / 60.0, 1) as minutes_since_update
    FROM silver.stg_payments
) staging_health
""",
    columns=(
        ColumnDefinition("table_name", "VARCHAR", "Table", filterable=True, groupby=True),
        ColumnDefinition("row_count", "BIGINT", "Row Count", filterable=False, groupby=False),
        ColumnDefinition(
            "latest_event",
            "TIMESTAMP",
            "Latest Event",
            is_dttm=True,
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "minutes_since_update",
            "DOUBLE",
            "Minutes Since Update",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "sum_rows",
            "SUM(row_count)",
            "Total Rows",
            d3format=",d",
        ),
        MetricDefinition(
            "max_staleness",
            "MAX(minutes_since_update)",
            "Max Staleness (min)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_staleness",
            "AVG(minutes_since_update)",
            "Avg Staleness (min)",
            d3format=",.1f",
        ),
    ),
    cache_timeout=60,
)


# Active trips from Silver layer
SILVER_ACTIVE_TRIPS = DatasetDefinition(
    name="silver_active_trips",
    description="Active trips currently in progress from staging table",
    sql="""
WITH latest_trip_states AS (
    SELECT
        trip_id,
        trip_state,
        timestamp,
        ROW_NUMBER() OVER (PARTITION BY trip_id ORDER BY timestamp DESC) AS rn
    FROM silver.stg_trips
    WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
)
SELECT
    trip_id,
    trip_state,
    timestamp
FROM latest_trip_states
WHERE rn = 1
  AND trip_state IN ('driver_en_route', 'driver_arrived', 'started')
""",
    columns=(
        ColumnDefinition("trip_id", "VARCHAR", "Trip ID", filterable=True, groupby=True),
        ColumnDefinition("trip_state", "VARCHAR", "State", filterable=True, groupby=True),
        ColumnDefinition(
            "timestamp",
            "TIMESTAMP",
            "Timestamp",
            is_dttm=True,
            filterable=True,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_active",
            "COUNT(*)",
            "Active Trips",
            d3format=",d",
        ),
    ),
    main_dttm_col="timestamp",
    cache_timeout=30,
)


# Stale drivers (zombie detection)
SILVER_STALE_DRIVERS = DatasetDefinition(
    name="silver_stale_drivers",
    description="Drivers marked active but not sending GPS updates",
    sql="""
SELECT
    driver_id,
    current_status,
    last_gps_timestamp,
    last_status_timestamp,
    minutes_since_last_ping
FROM silver.anomalies_zombie_drivers
""",
    columns=(
        ColumnDefinition("driver_id", "VARCHAR", "Driver ID", filterable=True, groupby=True),
        ColumnDefinition("current_status", "VARCHAR", "Status", filterable=True, groupby=True),
        ColumnDefinition(
            "last_gps_timestamp",
            "TIMESTAMP",
            "Last GPS",
            is_dttm=True,
            filterable=True,
            groupby=False,
        ),
        ColumnDefinition(
            "last_status_timestamp",
            "TIMESTAMP",
            "Last Status",
            is_dttm=True,
            filterable=True,
            groupby=False,
        ),
        ColumnDefinition(
            "minutes_since_last_ping",
            "DOUBLE",
            "Minutes Stale",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_stale",
            "COUNT(*)",
            "Stale Drivers",
            d3format=",d",
        ),
        MetricDefinition(
            "max_stale_minutes",
            "MAX(minutes_since_last_ping)",
            "Max Stale Time (min)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "avg_stale_minutes",
            "AVG(minutes_since_last_ping)",
            "Avg Stale Time (min)",
            d3format=",.1f",
        ),
    ),
    main_dttm_col="last_status_timestamp",
    cache_timeout=60,
)


# =============================================================================
# Data Quality Monitoring - KPI Datasets (LEGACY)
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
    # ==========================================================================
    # CONSOLIDATED DATASETS (new - with columns and metrics)
    # ==========================================================================
    SILVER_ANOMALIES,
    SILVER_STAGING_HEALTH,
    SILVER_ACTIVE_TRIPS,
    SILVER_STALE_DRIVERS,
    # ==========================================================================
    # LEGACY DATASETS (kept for backward compatibility during transition)
    # ==========================================================================
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
