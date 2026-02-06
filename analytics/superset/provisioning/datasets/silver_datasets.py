"""Silver layer dataset definitions for Superset provisioning.

These datasets query the Silver layer tables for Data Quality Monitoring dashboard
and some Platform Operations datasets.
All datasets use the consolidated pattern with proper column and metric definitions.
"""

from provisioning.dashboards.base import (
    ColumnDefinition,
    DatasetDefinition,
    MetricDefinition,
)


# =============================================================================
# Silver Layer - CONSOLIDATED DATASETS
# =============================================================================

# Consolidated anomalies dataset - for all data quality and error monitoring charts
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
    anomaly_details
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
        ColumnDefinition(
            "anomaly_details", "VARCHAR", "Anomaly Details", filterable=False, groupby=False
        ),
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
        MetricDefinition(
            "count_gps_outliers",
            "SUM(CASE WHEN anomaly_type = 'gps_outlier' THEN 1 ELSE 0 END)",
            "GPS Outliers",
            d3format=",d",
        ),
        MetricDefinition(
            "count_impossible_speeds",
            "SUM(CASE WHEN anomaly_type = 'impossible_speed' THEN 1 ELSE 0 END)",
            "Impossible Speeds",
            d3format=",d",
        ),
    ),
    main_dttm_col="detected_at",
    cache_timeout=60,
    allow_empty_results=True,
)


# Consolidated staging health dataset - for table health monitoring charts
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


# Active trips from Silver layer - for real-time trip monitoring
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


# Stale drivers (zombie detection) - for driver health monitoring
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
    allow_empty_results=True,
)


# =============================================================================
# All Silver Datasets
# =============================================================================

SILVER_DATASETS: tuple[DatasetDefinition, ...] = (
    SILVER_ANOMALIES,
    SILVER_STAGING_HEALTH,
    SILVER_ACTIVE_TRIPS,
    SILVER_STALE_DRIVERS,
)
