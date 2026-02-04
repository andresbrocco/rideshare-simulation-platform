"""Demand Analysis dashboard definition.

This dashboard visualizes demand patterns, surge pricing, and zone performance
for driver positioning and capacity planning.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.demand_analysis_charts import DEMAND_ANALYSIS_CHARTS
from ..charts.map_charts import DEMAND_ANALYSIS_MAP_CHARTS
from ..datasets.gold_datasets import (
    GOLD_AVG_SURGE_24H,
    GOLD_AVG_WAIT_TIME_24H,
    GOLD_HOURLY_DEMAND_PATTERN,
    GOLD_SURGE_EVENTS,
    GOLD_SURGE_TRENDS,
    GOLD_TOP_DEMAND_ZONES,
    GOLD_TOTAL_REQUESTS_24H,
    GOLD_WAIT_TIME_BY_ZONE,
    GOLD_ZONE_DEMAND_HEATMAP,
)
from ..datasets.map_datasets import (
    DEMAND_PICKUP_HOTSPOTS,
    DEMAND_SURGE_ZONES,
)

# Dataset tuple for this specific dashboard
DEMAND_ANALYSIS_DATASETS = (
    GOLD_ZONE_DEMAND_HEATMAP,
    GOLD_SURGE_TRENDS,
    GOLD_WAIT_TIME_BY_ZONE,
    GOLD_HOURLY_DEMAND_PATTERN,
    GOLD_TOP_DEMAND_ZONES,
    GOLD_SURGE_EVENTS,
    GOLD_TOTAL_REQUESTS_24H,
    GOLD_AVG_SURGE_24H,
    GOLD_AVG_WAIT_TIME_24H,
    # Map datasets
    DEMAND_PICKUP_HOTSPOTS,
    DEMAND_SURGE_ZONES,
)

# Combine standard charts with map charts
DEMAND_ANALYSIS_ALL_CHARTS = DEMAND_ANALYSIS_CHARTS + DEMAND_ANALYSIS_MAP_CHARTS

DEMAND_ANALYSIS_DASHBOARD = DashboardDefinition(
    title="Demand Analysis",
    slug="demand-analysis",
    description=(
        "Demand patterns, surge pricing, and zone performance analysis for "
        "driver positioning and capacity planning"
    ),
    datasets=DEMAND_ANALYSIS_DATASETS,
    charts=DEMAND_ANALYSIS_ALL_CHARTS,
    required_tables=(
        "gold.fact_trips",
        "gold.agg_hourly_zone_demand",
        "gold.agg_surge_history",
        "gold.dim_zones",
        "gold.dim_time",
        "silver.stg_surge_updates",
    ),
    refresh_interval=300,
)
