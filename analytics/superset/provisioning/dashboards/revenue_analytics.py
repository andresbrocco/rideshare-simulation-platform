"""Revenue Analytics dashboard definition.

This dashboard visualizes financial performance, revenue breakdown,
and payment analysis for business leadership.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.map_charts import REVENUE_ANALYTICS_MAP_CHARTS
from ..charts.revenue_analytics_charts import REVENUE_ANALYTICS_CHARTS
from ..datasets.gold_datasets import (
    GOLD_FACT_TRIPS,
    GOLD_PAYMENTS,
    GOLD_PLATFORM_REVENUE,
)
from ..datasets.map_datasets import REVENUE_LOCATION_MAP

# Dataset tuple for this specific dashboard - consolidated datasets only
REVENUE_ANALYTICS_DATASETS = (
    GOLD_PLATFORM_REVENUE,
    GOLD_PAYMENTS,
    GOLD_FACT_TRIPS,
    REVENUE_LOCATION_MAP,
)

# Combine standard charts with map charts
REVENUE_ANALYTICS_ALL_CHARTS = REVENUE_ANALYTICS_CHARTS + REVENUE_ANALYTICS_MAP_CHARTS

REVENUE_ANALYTICS_DASHBOARD = DashboardDefinition(
    title="Revenue Analytics",
    slug="revenue-analytics",
    description=(
        "Financial performance, revenue breakdown, and payment analysis " "for business leadership"
    ),
    datasets=REVENUE_ANALYTICS_DATASETS,
    charts=REVENUE_ANALYTICS_ALL_CHARTS,
    required_tables=(
        "gold.fact_trips",
        "gold.fact_payments",
        "gold.agg_daily_platform_revenue",
        "gold.dim_zones",
        "gold.dim_time",
        "gold.dim_payment_methods",
    ),
    refresh_interval=300,
)
