"""Revenue Analytics Dashboard (Gold layer).

Monitors:
- Revenue KPIs and trends
- Payment method distribution
- Zone revenue analysis
- Fare analysis
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

DAILY_REVENUE = DatasetDefinition(
    name="gold_daily_revenue",
    sql="""
    SELECT
        SUM(r.total_revenue) as daily_revenue,
        SUM(r.total_trips) as trip_count
    FROM gold.agg_daily_platform_revenue r
    JOIN gold.dim_time t ON r.time_key = t.time_key
    WHERE t.date_key = CURRENT_DATE
    """,
    description="Daily revenue total",
)

TOTAL_FEES = DatasetDefinition(
    name="gold_total_fees",
    sql="""
    SELECT
        SUM(r.total_platform_fees) as total_fees
    FROM gold.agg_daily_platform_revenue r
    JOIN gold.dim_time t ON r.time_key = t.time_key
    WHERE t.date_key = CURRENT_DATE
    """,
    description="Platform fees collected today",
)

TRIP_COUNT_TODAY = DatasetDefinition(
    name="gold_trip_count_today",
    sql="""
    SELECT
        SUM(r.total_trips) as trip_count
    FROM gold.agg_daily_platform_revenue r
    JOIN gold.dim_time t ON r.time_key = t.time_key
    WHERE t.date_key = CURRENT_DATE
    """,
    description="Total trips completed today",
)

REVENUE_BY_ZONE = DatasetDefinition(
    name="gold_revenue_by_zone",
    sql="""
    SELECT
        z.name AS zone_name,
        SUM(p.total_fare) as zone_revenue
    FROM gold.fact_payments p
    JOIN gold.fact_trips t ON p.trip_key = t.trip_key
    JOIN gold.dim_zones z ON t.pickup_zone_key = z.zone_key
    JOIN gold.dim_time dt ON p.time_key = dt.time_key
    WHERE dt.date_key = CURRENT_DATE
    GROUP BY z.name
    ORDER BY zone_revenue DESC
    LIMIT 10
    """,
    description="Revenue by pickup zone (today)",
)

REVENUE_OVER_TIME = DatasetDefinition(
    name="gold_revenue_over_time",
    sql="""
    SELECT
        t.date_key as date,
        r.total_revenue,
        r.total_platform_fees as platform_fees,
        r.total_driver_payouts as driver_earnings
    FROM gold.agg_daily_platform_revenue r
    JOIN gold.dim_time t ON r.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 14 DAYS
    ORDER BY date
    """,
    description="Revenue trend over 14 days",
)

AVG_FARE_BY_DISTANCE = DatasetDefinition(
    name="gold_avg_fare_by_distance",
    sql="""
    SELECT
        CASE
            WHEN t.distance_km < 2 THEN '0-2 km'
            WHEN t.distance_km < 5 THEN '2-5 km'
            WHEN t.distance_km < 10 THEN '5-10 km'
            WHEN t.distance_km < 20 THEN '10-20 km'
            ELSE '20+ km'
        END as distance_bucket,
        AVG(p.total_fare) as avg_fare,
        COUNT(*) as trip_count
    FROM gold.fact_payments p
    JOIN gold.fact_trips t ON p.trip_key = t.trip_key
    WHERE DATE(p.payment_timestamp) >= CURRENT_DATE - INTERVAL 7 DAYS
    AND t.distance_km IS NOT NULL
    GROUP BY
        CASE
            WHEN t.distance_km < 2 THEN '0-2 km'
            WHEN t.distance_km < 5 THEN '2-5 km'
            WHEN t.distance_km < 10 THEN '5-10 km'
            WHEN t.distance_km < 20 THEN '10-20 km'
            ELSE '20+ km'
        END
    ORDER BY MIN(t.distance_km)
    """,
    description="Average fare by distance bucket",
)

PAYMENT_METHODS = DatasetDefinition(
    name="gold_payment_methods",
    sql="""
    SELECT
        p.payment_method_type as payment_method,
        COUNT(*) as transaction_count,
        SUM(p.total_fare) as total_amount
    FROM gold.fact_payments p
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY p.payment_method_type
    ORDER BY total_amount DESC
    """,
    description="Payment method distribution",
)

REVENUE_BY_HOUR = DatasetDefinition(
    name="gold_revenue_by_hour",
    sql="""
    SELECT
        hour(p.payment_timestamp) as hour_of_day,
        t.date_key as date,
        SUM(p.total_fare) as hourly_revenue
    FROM gold.fact_payments p
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY hour(p.payment_timestamp), t.date_key
    ORDER BY date, hour_of_day
    """,
    description="Revenue heatmap by hour and date",
)

TOP_REVENUE_ZONES = DatasetDefinition(
    name="gold_top_revenue_zones",
    sql="""
    SELECT
        z.name AS zone_name,
        SUM(p.total_fare) as total_revenue,
        COUNT(*) as trip_count,
        AVG(p.total_fare) as avg_fare
    FROM gold.fact_payments p
    JOIN gold.fact_trips t ON p.trip_key = t.trip_key
    JOIN gold.dim_zones z ON t.pickup_zone_key = z.zone_key
    JOIN gold.dim_time dt ON p.time_key = dt.time_key
    WHERE dt.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY z.name
    ORDER BY total_revenue DESC
    LIMIT 10
    """,
    description="Top zones by revenue (7 days)",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    # KPI Row
    ChartDefinition(
        name="Daily Revenue",
        dataset_name="gold_daily_revenue",
        viz_type="big_number_total",
        metrics=("daily_revenue",),
        layout=(0, 0, 4, 3),
        extra_params={
            "color_picker": {"r": 0, "g": 128, "b": 0},
            "y_axis_format": "$,.2f",
        },
    ),
    ChartDefinition(
        name="Platform Fees",
        dataset_name="gold_total_fees",
        viz_type="big_number_total",
        metrics=("total_fees",),
        layout=(0, 4, 4, 3),
        extra_params={"y_axis_format": "$,.2f"},
    ),
    ChartDefinition(
        name="Trips Today",
        dataset_name="gold_trip_count_today",
        viz_type="big_number_total",
        metrics=("trip_count",),
        layout=(0, 8, 4, 3),
        extra_params={"color_picker": {"r": 0, "g": 128, "b": 255}},
    ),
    # Charts Row 1
    ChartDefinition(
        name="Revenue by Zone",
        dataset_name="gold_revenue_by_zone",
        viz_type="echarts_bar",
        metrics=("zone_revenue",),
        dimensions=("zone_name",),
        layout=(3, 0, 6, 4),
        extra_params={"y_axis_format": "$,.2f"},
    ),
    ChartDefinition(
        name="Revenue Trend",
        dataset_name="gold_revenue_over_time",
        viz_type="echarts_timeseries_line",
        metrics=("total_revenue", "platform_fees", "driver_earnings"),
        time_column="date",
        time_range="Last 14 days",
        layout=(3, 6, 6, 4),
        extra_params={"y_axis_format": "$,.2f"},
    ),
    # Charts Row 2
    ChartDefinition(
        name="Avg Fare by Distance",
        dataset_name="gold_avg_fare_by_distance",
        viz_type="echarts_bar",
        metrics=("avg_fare",),
        dimensions=("distance_bucket",),
        layout=(7, 0, 4, 4),
        extra_params={"y_axis_format": "$,.2f"},
    ),
    ChartDefinition(
        name="Payment Methods",
        dataset_name="gold_payment_methods",
        viz_type="pie",
        metrics=("total_amount",),
        dimensions=("payment_method",),
        layout=(7, 4, 4, 4),
    ),
    ChartDefinition(
        name="Revenue Heatmap",
        dataset_name="gold_revenue_by_hour",
        viz_type="heatmap",
        metrics=("hourly_revenue",),
        dimensions=("date", "hour_of_day"),
        layout=(7, 8, 4, 4),
    ),
    # Bottom Row
    ChartDefinition(
        name="Top Revenue Zones",
        dataset_name="gold_top_revenue_zones",
        viz_type="table",
        metrics=(),
        dimensions=("zone_name", "total_revenue", "trip_count", "avg_fare"),
        layout=(11, 0, 12, 4),
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

REVENUE_ANALYTICS_DASHBOARD = DashboardDefinition(
    title="Revenue Analytics",
    slug="revenue-analytics",
    datasets=(
        DAILY_REVENUE,
        TOTAL_FEES,
        TRIP_COUNT_TODAY,
        REVENUE_BY_ZONE,
        REVENUE_OVER_TIME,
        AVG_FARE_BY_DISTANCE,
        PAYMENT_METHODS,
        REVENUE_BY_HOUR,
        TOP_REVENUE_ZONES,
    ),
    charts=CHARTS,
    required_tables=(
        "gold.agg_daily_platform_revenue",
        "gold.fact_payments",
        "gold.fact_trips",
        "gold.dim_zones",
        "gold.dim_payment_methods",
    ),
    refresh_interval=300,
    description="Revenue metrics, trends, and payment analytics",
)
