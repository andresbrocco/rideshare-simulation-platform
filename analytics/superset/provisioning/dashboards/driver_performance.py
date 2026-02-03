"""Driver Performance Dashboard (Gold layer).

Monitors:
- Driver metrics and rankings
- Ratings distribution
- Utilization patterns
- Payout analysis
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

TOP_DRIVERS_BY_TRIPS = DatasetDefinition(
    name="gold_top_drivers_trips",
    sql="""
    SELECT
        d.driver_id,
        COALESCE(CONCAT(d.first_name, ' ', d.last_name), CONCAT('Driver-', SUBSTRING(d.driver_id, 1, 8))) as driver_name,
        SUM(p.trips_completed) as total_trips,
        AVG(p.avg_rating) as avg_rating,
        SUM(p.total_payout) as total_earnings
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_key = d.driver_key AND d.current_flag = true
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.driver_id, d.first_name, d.last_name
    ORDER BY total_trips DESC
    LIMIT 10
    """,
    description="Top 10 drivers by trip count (last 7 days)",
)

RATINGS_DISTRIBUTION = DatasetDefinition(
    name="gold_ratings_distribution",
    sql="""
    SELECT
        CAST(FLOOR(rating) AS INT) as rating_bucket,
        COUNT(*) as count
    FROM gold.fact_ratings
    WHERE rating_timestamp >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY CAST(FLOOR(rating) AS INT)
    ORDER BY rating_bucket
    """,
    description="Distribution of driver ratings",
)

DRIVER_PAYOUTS = DatasetDefinition(
    name="gold_driver_payouts",
    sql="""
    SELECT
        t.date_key as date,
        SUM(p.total_payout) as daily_payouts,
        COUNT(DISTINCT p.driver_key) as active_drivers
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 14 DAYS
    GROUP BY t.date_key
    ORDER BY t.date_key
    """,
    description="Daily driver payouts over time",
)

DRIVER_UTILIZATION = DatasetDefinition(
    name="gold_driver_utilization",
    sql="""
    SELECT
        t.date_key as date,
        COALESCE(CONCAT(d.first_name, ' ', d.last_name), CONCAT('Driver-', SUBSTRING(d.driver_id, 1, 8))) as driver_name,
        p.utilization_pct as utilization_rate
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_key = d.driver_key AND d.current_flag = true
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    AND p.utilization_pct > 0
    ORDER BY t.date_key, p.utilization_pct DESC
    LIMIT 100
    """,
    description="Driver utilization heatmap data",
)

TRIPS_VS_EARNINGS = DatasetDefinition(
    name="gold_trips_vs_earnings",
    sql="""
    SELECT
        d.driver_id,
        COALESCE(CONCAT(d.first_name, ' ', d.last_name), CONCAT('Driver-', SUBSTRING(d.driver_id, 1, 8))) as driver_name,
        SUM(p.trips_completed) as trips,
        SUM(p.total_payout) as earnings
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_key = d.driver_key AND d.current_flag = true
    JOIN gold.dim_time t ON p.time_key = t.time_key
    WHERE t.date_key >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.driver_id, d.first_name, d.last_name
    HAVING SUM(p.trips_completed) > 0
    """,
    description="Trips vs earnings scatter plot data",
)

DRIVER_STATUS_SUMMARY = DatasetDefinition(
    name="gold_driver_status_summary",
    sql="""
    SELECT
        shift_preference as status,
        COUNT(*) as driver_count
    FROM gold.dim_drivers
    WHERE current_flag = true
    GROUP BY shift_preference
    ORDER BY driver_count DESC
    """,
    description="Current driver status distribution (by shift preference)",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        name="Top 10 Drivers by Trips",
        dataset_name="gold_top_drivers_trips",
        viz_type="echarts_bar",
        metrics=("total_trips",),
        dimensions=("driver_name",),
        layout=(0, 0, 6, 4),
        extra_params={"bar_stacked": False, "show_legend": False},
    ),
    ChartDefinition(
        name="Ratings Distribution",
        dataset_name="gold_ratings_distribution",
        viz_type="echarts_bar",
        metrics=("count",),
        dimensions=("rating_bucket",),
        layout=(0, 6, 6, 4),
        extra_params={"x_axis_label": "Rating", "y_axis_label": "Count"},
    ),
    ChartDefinition(
        name="Daily Driver Payouts",
        dataset_name="gold_driver_payouts",
        viz_type="echarts_timeseries_line",
        metrics=("daily_payouts",),
        time_column="date",
        time_range="Last 14 days",
        layout=(4, 0, 6, 4),
        extra_params={"y_axis_format": "$,.2f"},
    ),
    ChartDefinition(
        name="Driver Utilization Heatmap",
        dataset_name="gold_driver_utilization",
        viz_type="heatmap",
        metrics=("utilization_rate",),
        dimensions=("date", "driver_name"),
        layout=(4, 6, 6, 4),
    ),
    ChartDefinition(
        name="Trips vs Earnings",
        dataset_name="gold_trips_vs_earnings",
        viz_type="echarts_scatter",
        metrics=("earnings",),
        dimensions=("trips",),
        layout=(8, 0, 6, 4),
        extra_params={"entity": "driver_name"},
    ),
    ChartDefinition(
        name="Driver Status",
        dataset_name="gold_driver_status_summary",
        viz_type="pie",
        metrics=("driver_count",),
        dimensions=("status",),
        layout=(8, 6, 6, 4),
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

DRIVER_PERFORMANCE_DASHBOARD = DashboardDefinition(
    title="Driver Performance",
    slug="driver-performance",
    datasets=(
        TOP_DRIVERS_BY_TRIPS,
        RATINGS_DISTRIBUTION,
        DRIVER_PAYOUTS,
        DRIVER_UTILIZATION,
        TRIPS_VS_EARNINGS,
        DRIVER_STATUS_SUMMARY,
    ),
    charts=CHARTS,
    required_tables=(
        "gold.agg_daily_driver_performance",
        "gold.dim_drivers",
        "gold.dim_time",
        "gold.fact_ratings",
    ),
    refresh_interval=300,
    description="Driver metrics, ratings, and performance analytics",
)
