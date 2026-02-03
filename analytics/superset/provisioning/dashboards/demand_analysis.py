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
        z.name AS zone_name,
        DATE(d.hour_timestamp) as date,
        SUM(d.requested_trips) as total_requests,
        AVG(d.avg_surge_multiplier) as avg_surge
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_key = z.zone_key
    WHERE d.hour_timestamp >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY z.name, DATE(d.hour_timestamp)
    ORDER BY date, total_requests DESC
    """,
    description="Zone demand heatmap by date",
)

SURGE_TRENDS = DatasetDefinition(
    name="gold_surge_trends",
    sql="""
    SELECT
        hour_timestamp as hour,
        avg_surge_multiplier as avg_surge,
        max_surge_multiplier as max_surge
    FROM gold.agg_surge_history
    WHERE hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
    ORDER BY hour
    """,
    description="Surge multiplier trends over time",
)

WAIT_TIME_BY_ZONE = DatasetDefinition(
    name="gold_wait_time_by_zone",
    sql="""
    SELECT
        z.name AS zone_name,
        AVG(d.avg_wait_time_minutes) as avg_wait_minutes
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_key = z.zone_key
    WHERE d.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY z.name
    ORDER BY avg_wait_minutes DESC
    LIMIT 15
    """,
    description="Average wait time by zone",
)

HOURLY_DEMAND_PATTERN = DatasetDefinition(
    name="gold_hourly_demand_pattern",
    sql="""
    SELECT
        hour(hour_timestamp) as hour_of_day,
        SUM(requested_trips) as total_requests,
        SUM(completed_trips) as completed
    FROM gold.agg_hourly_zone_demand
    WHERE hour_timestamp >= current_timestamp - INTERVAL 7 DAYS
    GROUP BY hour(hour_timestamp)
    ORDER BY hour_of_day
    """,
    description="Demand by hour of day (weekly aggregate)",
)

TOP_DEMAND_ZONES = DatasetDefinition(
    name="gold_top_demand_zones",
    sql="""
    SELECT
        z.name AS zone_name,
        SUM(d.requested_trips) as total_requests,
        SUM(d.completed_trips) as completed,
        ROUND(SUM(d.completed_trips) * 100.0 / NULLIF(SUM(d.requested_trips), 0), 1) as fulfillment_rate
    FROM gold.agg_hourly_zone_demand d
    JOIN gold.dim_zones z ON d.zone_key = z.zone_key
    WHERE d.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY z.name
    ORDER BY total_requests DESC
    LIMIT 10
    """,
    description="Top zones by demand (24h)",
)

SURGE_EVENTS = DatasetDefinition(
    name="gold_surge_events",
    sql="""
    SELECT
        s.hour_timestamp as hour,
        z.name AS zone_name,
        s.max_surge_multiplier as peak_surge,
        s.surge_update_count as surge_updates
    FROM gold.agg_surge_history s
    JOIN gold.dim_zones z ON s.zone_key = z.zone_key
    WHERE s.hour_timestamp >= current_timestamp - INTERVAL 24 HOURS
    AND s.max_surge_multiplier > 1.5
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
