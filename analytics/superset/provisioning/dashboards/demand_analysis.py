"""Demand Analysis Dashboard (Gold layer).

Monitors:
- Zone-level demand patterns
- Surge pricing trends
- Wait time analysis
- Temporal demand patterns
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

ZONE_DEMAND_HEATMAP = DatasetDefinition(
    name="gold_zone_demand_heatmap",
    sql="""
    SELECT
        z.zone_name,
        DATE(d.hour) as date,
        SUM(d.trip_requests) as total_requests,
        AVG(d.avg_surge_multiplier) as avg_surge
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_id = z.zone_id
    WHERE d.hour >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY z.zone_name, DATE(d.hour)
    ORDER BY date, total_requests DESC
    """,
    description="Zone demand heatmap by date",
)

SURGE_TRENDS = DatasetDefinition(
    name="gold_surge_trends",
    sql="""
    SELECT
        date_trunc('hour', effective_at) as hour,
        AVG(surge_multiplier) as avg_surge,
        MAX(surge_multiplier) as max_surge
    FROM gold.agg_surge_history
    WHERE effective_at >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY date_trunc('hour', effective_at)
    ORDER BY hour
    """,
    description="Surge multiplier trends over time",
)

WAIT_TIME_BY_ZONE = DatasetDefinition(
    name="gold_wait_time_by_zone",
    sql="""
    SELECT
        z.zone_name,
        AVG(d.avg_wait_time_seconds) / 60 as avg_wait_minutes
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_id = z.zone_id
    WHERE d.hour >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY z.zone_name
    ORDER BY avg_wait_minutes DESC
    LIMIT 15
    """,
    description="Average wait time by zone",
)

HOURLY_DEMAND_PATTERN = DatasetDefinition(
    name="gold_hourly_demand_pattern",
    sql="""
    SELECT
        HOUR(hour) as hour_of_day,
        SUM(trip_requests) as total_requests,
        SUM(trips_completed) as completed,
        SUM(trips_cancelled) as cancelled
    FROM gold.agg_hourly_zone_demand
    WHERE hour >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY HOUR(hour)
    ORDER BY hour_of_day
    """,
    description="Demand by hour of day (weekly aggregate)",
)

TOP_DEMAND_ZONES = DatasetDefinition(
    name="gold_top_demand_zones",
    sql="""
    SELECT
        z.zone_name,
        SUM(d.trip_requests) as total_requests,
        SUM(d.trips_completed) as completed,
        ROUND(SUM(d.trips_completed) * 100.0 / NULLIF(SUM(d.trip_requests), 0), 1) as fulfillment_rate
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_id = z.zone_id
    WHERE d.hour >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY z.zone_name
    ORDER BY total_requests DESC
    LIMIT 10
    """,
    description="Top zones by demand (24h)",
)

SURGE_EVENTS = DatasetDefinition(
    name="gold_surge_events",
    sql="""
    SELECT
        date_trunc('hour', effective_at) as hour,
        z.zone_name,
        MAX(surge_multiplier) as peak_surge,
        COUNT(*) as surge_updates
    FROM gold.agg_surge_history s
    JOIN gold.dim_zones z ON s.zone_id = z.zone_id
    WHERE s.effective_at >= current_timestamp - INTERVAL 24 HOURS
    AND s.surge_multiplier > 1.5
    GROUP BY date_trunc('hour', effective_at), z.zone_name
    ORDER BY hour, peak_surge DESC
    """,
    description="Surge events timeline (>1.5x)",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        name="Zone Demand Heatmap",
        dataset_name="gold_zone_demand_heatmap",
        viz_type="heatmap",
        metrics=("total_requests",),
        dimensions=("date", "zone_name"),
        layout=(0, 0, 6, 4),
    ),
    ChartDefinition(
        name="Surge Multiplier Trends",
        dataset_name="gold_surge_trends",
        viz_type="echarts_timeseries_line",
        metrics=("avg_surge", "max_surge"),
        time_column="hour",
        time_range="Last 24 hours",
        layout=(0, 6, 6, 4),
        extra_params={"y_axis_format": ",.2f"},
    ),
    ChartDefinition(
        name="Wait Time by Zone",
        dataset_name="gold_wait_time_by_zone",
        viz_type="echarts_bar",
        metrics=("avg_wait_minutes",),
        dimensions=("zone_name",),
        layout=(4, 0, 6, 4),
        extra_params={"y_axis_label": "Minutes"},
    ),
    ChartDefinition(
        name="Hourly Demand Pattern",
        dataset_name="gold_hourly_demand_pattern",
        viz_type="echarts_area",
        metrics=("total_requests", "completed"),
        dimensions=("hour_of_day",),
        layout=(4, 6, 6, 4),
        extra_params={"stack": False},
    ),
    ChartDefinition(
        name="Top Demand Zones",
        dataset_name="gold_top_demand_zones",
        viz_type="table",
        metrics=(),
        dimensions=("zone_name", "total_requests", "completed", "fulfillment_rate"),
        layout=(8, 0, 6, 4),
    ),
    ChartDefinition(
        name="Surge Events Timeline",
        dataset_name="gold_surge_events",
        viz_type="echarts_timeseries_bar",
        metrics=("surge_updates",),
        dimensions=("zone_name",),
        time_column="hour",
        time_range="Last 24 hours",
        layout=(8, 6, 6, 4),
        extra_params={"stack": True},
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

DEMAND_ANALYSIS_DASHBOARD = DashboardDefinition(
    title="Demand Analysis",
    slug="demand-analysis",
    datasets=(
        ZONE_DEMAND_HEATMAP,
        SURGE_TRENDS,
        WAIT_TIME_BY_ZONE,
        HOURLY_DEMAND_PATTERN,
        TOP_DEMAND_ZONES,
        SURGE_EVENTS,
    ),
    charts=CHARTS,
    required_tables=(
        "gold.agg_hourly_zone_demand",
        "gold.agg_surge_history",
        "gold.dim_zones",
    ),
    refresh_interval=300,
    description="Zone demand patterns and surge pricing analysis",
)
