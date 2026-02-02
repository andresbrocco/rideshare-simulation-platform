"""Data Quality Monitoring Dashboard (Silver layer).

Monitors:
- Anomaly detection results
- Data validation metrics
- Staging table freshness
- Quality indicators
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

TOTAL_ANOMALIES = DatasetDefinition(
    name="silver_total_anomalies",
    sql="""
    SELECT COUNT(*) as total_anomalies
    FROM silver.anomalies_all
    WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
    """,
    description="Total anomalies detected in last 24 hours",
)

ANOMALIES_BY_TYPE = DatasetDefinition(
    name="silver_anomalies_by_type",
    sql="""
    SELECT
        anomaly_type,
        COUNT(*) as count
    FROM silver.anomalies_all
    WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY anomaly_type
    ORDER BY count DESC
    """,
    description="Anomaly distribution by type",
)

ANOMALIES_OVER_TIME = DatasetDefinition(
    name="silver_anomalies_over_time",
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
    description="Hourly anomaly trend by type",
)

GPS_OUTLIERS_COUNT = DatasetDefinition(
    name="silver_gps_outliers",
    sql="""
    SELECT COUNT(*) as outlier_count
    FROM silver.anomalies_gps_outliers
    WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
    """,
    description="GPS coordinates outside Sao Paulo bounds",
)

IMPOSSIBLE_SPEEDS_COUNT = DatasetDefinition(
    name="silver_impossible_speeds",
    sql="""
    SELECT COUNT(*) as speed_violations
    FROM silver.anomalies_impossible_speeds
    WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
    """,
    description="Speeds exceeding 200 km/h",
)

ZOMBIE_DRIVERS = DatasetDefinition(
    name="silver_zombie_drivers",
    sql="""
    SELECT
        driver_id,
        last_seen,
        UNIX_TIMESTAMP(current_timestamp) - UNIX_TIMESTAMP(last_seen) as seconds_since_seen
    FROM silver.anomalies_zombie_drivers
    WHERE detected_at >= current_timestamp - INTERVAL 24 HOURS
    ORDER BY seconds_since_seen DESC
    LIMIT 20
    """,
    description="Drivers with no GPS for 10+ minutes",
)

STAGING_ROW_COUNTS = DatasetDefinition(
    name="silver_staging_row_counts",
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
    description="Row counts per staging table",
)

STAGING_FRESHNESS = DatasetDefinition(
    name="silver_staging_freshness",
    sql="""
    SELECT table_name, latest_update
    FROM (
        SELECT 'stg_trips' as table_name, MAX(updated_at) as latest_update FROM silver.stg_trips
        UNION ALL
        SELECT 'stg_gps_pings' as table_name, MAX(recorded_at) as latest_update FROM silver.stg_gps_pings
        UNION ALL
        SELECT 'stg_driver_status' as table_name, MAX(updated_at) as latest_update FROM silver.stg_driver_status
        UNION ALL
        SELECT 'stg_surge_updates' as table_name, MAX(updated_at) as latest_update FROM silver.stg_surge_updates
        UNION ALL
        SELECT 'stg_ratings' as table_name, MAX(created_at) as latest_update FROM silver.stg_ratings
        UNION ALL
        SELECT 'stg_payments' as table_name, MAX(processed_at) as latest_update FROM silver.stg_payments
    ) freshness
    ORDER BY latest_update DESC
    """,
    description="Latest update per staging table",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        name="Total Anomalies (24h)",
        dataset_name="silver_total_anomalies",
        viz_type="big_number_total",
        metrics=("total_anomalies",),
        layout=(0, 0, 3, 3),
        extra_params={"color_picker": {"r": 255, "g": 165, "b": 0}},  # Orange
    ),
    ChartDefinition(
        name="GPS Outliers",
        dataset_name="silver_gps_outliers",
        viz_type="big_number_total",
        metrics=("outlier_count",),
        layout=(0, 3, 3, 3),
    ),
    ChartDefinition(
        name="Impossible Speeds",
        dataset_name="silver_impossible_speeds",
        viz_type="big_number_total",
        metrics=("speed_violations",),
        layout=(0, 6, 3, 3),
    ),
    ChartDefinition(
        name="Anomalies by Type",
        dataset_name="silver_anomalies_by_type",
        viz_type="pie",
        metrics=("count",),
        dimensions=("anomaly_type",),
        layout=(0, 9, 3, 3),
    ),
    ChartDefinition(
        name="Anomalies Over Time",
        dataset_name="silver_anomalies_over_time",
        viz_type="echarts_timeseries_line",
        metrics=("count",),
        dimensions=("anomaly_type",),
        time_column="hour",
        time_range="Last 24 hours",
        layout=(3, 0, 6, 4),
    ),
    ChartDefinition(
        name="Staging Table Sizes",
        dataset_name="silver_staging_row_counts",
        viz_type="echarts_bar",
        metrics=("row_count",),
        dimensions=("table_name",),
        layout=(3, 6, 6, 4),
    ),
    ChartDefinition(
        name="Zombie Drivers",
        dataset_name="silver_zombie_drivers",
        viz_type="table",
        metrics=(),
        dimensions=("driver_id", "last_seen", "seconds_since_seen"),
        layout=(7, 0, 6, 4),
    ),
    ChartDefinition(
        name="Data Freshness",
        dataset_name="silver_staging_freshness",
        viz_type="table",
        metrics=(),
        dimensions=("table_name", "latest_update"),
        layout=(7, 6, 6, 4),
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

DATA_QUALITY_DASHBOARD = DashboardDefinition(
    title="Data Quality Monitoring",
    slug="silver-quality",
    datasets=(
        TOTAL_ANOMALIES,
        ANOMALIES_BY_TYPE,
        ANOMALIES_OVER_TIME,
        GPS_OUTLIERS_COUNT,
        IMPOSSIBLE_SPEEDS_COUNT,
        ZOMBIE_DRIVERS,
        STAGING_ROW_COUNTS,
        STAGING_FRESHNESS,
    ),
    charts=CHARTS,
    required_tables=(
        "silver.anomalies_all",
        "silver.anomalies_gps_outliers",
        "silver.stg_trips",
    ),
    refresh_interval=300,
    description="Monitor Silver layer data quality and anomaly detection",
)
