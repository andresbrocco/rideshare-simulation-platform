"""Demand Analysis dashboard definition.

This dashboard visualizes demand patterns, surge pricing, and zone performance
for driver positioning and capacity planning.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.demand_analysis_charts import DEMAND_ANALYSIS_CHARTS
from ..charts.map_charts import DEMAND_ANALYSIS_MAP_CHARTS
from ..datasets.gold_datasets import (
    GOLD_HOURLY_ZONE_DEMAND,
    GOLD_SURGE_HISTORY,
)
from ..datasets.map_datasets import (
    DEMAND_PICKUP_HOTSPOTS,
    DEMAND_SURGE_ZONES,
)

# Dataset tuple for this specific dashboard - consolidated datasets only
DEMAND_ANALYSIS_DATASETS = (
    GOLD_HOURLY_ZONE_DEMAND,
    GOLD_SURGE_HISTORY,
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
