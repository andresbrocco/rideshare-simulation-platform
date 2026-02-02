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
        COALESCE(d.display_name, CONCAT('Driver-', SUBSTRING(d.driver_id, 1, 8))) as driver_name,
        p.total_trips,
        p.avg_rating,
        p.total_earnings
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_id = d.driver_id AND d.is_current = true
    WHERE p.date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY d.driver_id, d.display_name, p.total_trips, p.avg_rating, p.total_earnings
    ORDER BY p.total_trips DESC
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
    WHERE created_at >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY CAST(FLOOR(rating) AS INT)
    ORDER BY rating_bucket
    """,
    description="Distribution of driver ratings",
)

DRIVER_PAYOUTS = DatasetDefinition(
    name="gold_driver_payouts",
    sql="""
    SELECT
        date,
        SUM(total_earnings) as daily_payouts,
        COUNT(DISTINCT driver_id) as active_drivers
    FROM gold.agg_daily_driver_performance
    WHERE date >= CURRENT_DATE - INTERVAL 14 DAYS
    GROUP BY date
    ORDER BY date
    """,
    description="Daily driver payouts over time",
)

DRIVER_UTILIZATION = DatasetDefinition(
    name="gold_driver_utilization",
    sql="""
    SELECT
        p.date,
        COALESCE(d.display_name, CONCAT('Driver-', SUBSTRING(p.driver_id, 1, 8))) as driver_name,
        p.utilization_rate
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_id = d.driver_id AND d.is_current = true
    WHERE p.date >= CURRENT_DATE - INTERVAL 7 DAYS
    AND p.utilization_rate > 0
    ORDER BY p.date, p.utilization_rate DESC
    LIMIT 100
    """,
    description="Driver utilization heatmap data",
)

TRIPS_VS_EARNINGS = DatasetDefinition(
    name="gold_trips_vs_earnings",
    sql="""
    SELECT
        p.driver_id,
        COALESCE(d.display_name, CONCAT('Driver-', SUBSTRING(p.driver_id, 1, 8))) as driver_name,
        SUM(p.total_trips) as trips,
        SUM(p.total_earnings) as earnings
    FROM gold.agg_daily_driver_performance p
    JOIN gold.dim_drivers d ON p.driver_id = d.driver_id AND d.is_current = true
    WHERE p.date >= CURRENT_DATE - INTERVAL 7 DAYS
    GROUP BY p.driver_id, d.display_name
    HAVING SUM(p.total_trips) > 0
    """,
    description="Trips vs earnings scatter plot data",
)

DRIVER_STATUS_SUMMARY = DatasetDefinition(
    name="gold_driver_status_summary",
    sql="""
    SELECT
        status,
        COUNT(*) as driver_count
    FROM gold.dim_drivers
    WHERE is_current = true
    GROUP BY status
    ORDER BY driver_count DESC
    """,
    description="Current driver status distribution",
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
        "gold.fact_ratings",
    ),
    refresh_interval=300,
    description="Driver metrics, ratings, and performance analytics",
)
