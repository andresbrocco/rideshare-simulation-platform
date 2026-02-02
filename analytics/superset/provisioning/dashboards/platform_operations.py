"""Platform Operations Dashboard (Gold layer).

Monitors:
- Real-time trip activity
- Platform KPIs
- Zone-level metrics
- Pipeline health
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

ACTIVE_TRIPS = DatasetDefinition(
    name="gold_active_trips",
    sql="""
    SELECT COUNT(*) as active_trips
    FROM gold.fact_trips
    WHERE status IN ('REQUESTED', 'MATCHED', 'DRIVER_EN_ROUTE', 'DRIVER_ARRIVED', 'STARTED')
    """,
    description="Currently active trips",
)

COMPLETED_TODAY = DatasetDefinition(
    name="gold_completed_today",
    sql="""
    SELECT COUNT(*) as completed_trips
    FROM gold.fact_trips
    WHERE status = 'COMPLETED'
    AND DATE(completed_at) = CURRENT_DATE
    """,
    description="Trips completed today",
)

AVERAGE_WAIT_TIME = DatasetDefinition(
    name="gold_average_wait_time",
    sql="""
    SELECT
        AVG(UNIX_TIMESTAMP(pickup_at) - UNIX_TIMESTAMP(requested_at)) / 60 as avg_wait_minutes
    FROM gold.fact_trips
    WHERE status = 'COMPLETED'
    AND DATE(completed_at) = CURRENT_DATE
    AND pickup_at IS NOT NULL
    AND requested_at IS NOT NULL
    """,
    description="Average wait time in minutes",
)

TOTAL_REVENUE_TODAY = DatasetDefinition(
    name="gold_total_revenue_today",
    sql="""
    SELECT
        SUM(total_amount) as total_revenue
    FROM gold.fact_payments
    WHERE DATE(processed_at) = CURRENT_DATE
    AND payment_status = 'completed'
    """,
    description="Total revenue today",
)

HOURLY_TRIP_VOLUME = DatasetDefinition(
    name="gold_hourly_trip_volume",
    sql="""
    SELECT
        date_trunc('hour', requested_at) as hour,
        COUNT(*) as trip_count
    FROM gold.fact_trips
    WHERE requested_at >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY date_trunc('hour', requested_at)
    ORDER BY hour
    """,
    description="Hourly trip volume (24h)",
)

TRIPS_BY_ZONE = DatasetDefinition(
    name="gold_trips_by_zone",
    sql="""
    SELECT
        z.zone_name,
        COUNT(*) as trip_count
    FROM gold.fact_trips t
    JOIN gold.dim_zones z ON t.pickup_zone_id = z.zone_id
    WHERE DATE(t.requested_at) = CURRENT_DATE
    GROUP BY z.zone_name
    ORDER BY trip_count DESC
    LIMIT 10
    """,
    description="Trip distribution by zone (today)",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        name="Active Trips",
        dataset_name="gold_active_trips",
        viz_type="big_number_total",
        metrics=("active_trips",),
        layout=(0, 0, 3, 3),
        extra_params={"color_picker": {"r": 0, "g": 128, "b": 255}},  # Blue
    ),
    ChartDefinition(
        name="Completed Today",
        dataset_name="gold_completed_today",
        viz_type="big_number_total",
        metrics=("completed_trips",),
        layout=(0, 3, 3, 3),
        extra_params={"color_picker": {"r": 0, "g": 200, "b": 0}},  # Green
    ),
    ChartDefinition(
        name="Avg Wait Time (min)",
        dataset_name="gold_average_wait_time",
        viz_type="big_number_total",
        metrics=("avg_wait_minutes",),
        layout=(0, 6, 3, 3),
    ),
    ChartDefinition(
        name="Revenue Today",
        dataset_name="gold_total_revenue_today",
        viz_type="big_number_total",
        metrics=("total_revenue",),
        layout=(0, 9, 3, 3),
        extra_params={
            "color_picker": {"r": 0, "g": 128, "b": 0},
            "y_axis_format": "$,.2f",
        },
    ),
    ChartDefinition(
        name="Hourly Trip Volume",
        dataset_name="gold_hourly_trip_volume",
        viz_type="echarts_timeseries_bar",
        metrics=("trip_count",),
        time_column="hour",
        time_range="Last 24 hours",
        layout=(3, 0, 6, 4),
    ),
    ChartDefinition(
        name="Top Zones by Trips",
        dataset_name="gold_trips_by_zone",
        viz_type="echarts_bar",
        metrics=("trip_count",),
        dimensions=("zone_name",),
        layout=(3, 6, 6, 4),
        extra_params={"bar_stacked": False},
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

PLATFORM_OPERATIONS_DASHBOARD = DashboardDefinition(
    title="Platform Operations",
    slug="operations",
    datasets=(
        ACTIVE_TRIPS,
        COMPLETED_TODAY,
        AVERAGE_WAIT_TIME,
        TOTAL_REVENUE_TODAY,
        HOURLY_TRIP_VOLUME,
        TRIPS_BY_ZONE,
    ),
    charts=CHARTS,
    required_tables=(
        "gold.fact_trips",
        "gold.fact_payments",
        "gold.dim_zones",
    ),
    refresh_interval=60,  # 1 minute for real-time monitoring
    description="Real-time platform operations monitoring",
)
