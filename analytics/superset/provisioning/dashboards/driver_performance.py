"""Driver Performance dashboard definition.

This dashboard tracks driver metrics, ratings, and utilization analysis
to optimize the driver network.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.driver_performance_charts import DRIVER_PERFORMANCE_CHARTS
from ..charts.map_charts import DRIVER_PERFORMANCE_MAP_CHARTS
from ..datasets.gold_datasets import (
    DS_ACTIVE_DRIVERS,
    DS_PAYOUT_TRENDS,
    DS_RATING_DISTRIBUTION,
    DS_TOP_DRIVERS,
    DS_TRIPS_VS_EARNINGS,
    DS_UTILIZATION_HEATMAP,
)
from ..datasets.map_datasets import DP_DRIVER_HOME_LOCATIONS

# Dataset tuple for this specific dashboard
DRIVER_PERFORMANCE_DATASETS = (
    DS_ACTIVE_DRIVERS,
    DS_PAYOUT_TRENDS,
    DS_TOP_DRIVERS,
    DS_RATING_DISTRIBUTION,
    DS_UTILIZATION_HEATMAP,
    DS_TRIPS_VS_EARNINGS,
    # Map dataset
    DP_DRIVER_HOME_LOCATIONS,
)

# Combine standard charts with map charts
DRIVER_PERFORMANCE_ALL_CHARTS = DRIVER_PERFORMANCE_CHARTS + DRIVER_PERFORMANCE_MAP_CHARTS

DRIVER_PERFORMANCE_DASHBOARD = DashboardDefinition(
    title="Driver Performance",
    slug="driver-performance",
    description=(
        "Driver metrics, ratings, and utilization analysis. Tracks driver "
        "performance, earnings, and efficiency to optimize the driver network."
    ),
    datasets=DRIVER_PERFORMANCE_DATASETS,
    charts=DRIVER_PERFORMANCE_ALL_CHARTS,
    required_tables=(
        "gold.fact_trips",
        "gold.fact_payments",
        "gold.fact_ratings",
        "gold.fact_driver_activity",
        "gold.agg_daily_driver_performance",
        "gold.dim_drivers",
        "gold.dim_time",
    ),
    refresh_interval=300,
)
