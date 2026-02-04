"""Revenue Analytics dashboard definition.

This dashboard visualizes financial performance, revenue breakdown,
and payment analysis for business leadership.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.map_charts import REVENUE_ANALYTICS_MAP_CHARTS
from ..charts.revenue_analytics_charts import REVENUE_ANALYTICS_CHARTS
from ..datasets.gold_datasets import (
    # Consolidated datasets
    GOLD_PAYMENTS,
    GOLD_PLATFORM_REVENUE,
    # Legacy datasets (for charts not yet migrated)
    GOLD_DAILY_REVENUE,
    GOLD_FARE_VS_DURATION,
    GOLD_PAYMENT_METHOD_MIX,
    GOLD_PLATFORM_FEES,
    GOLD_REVENUE_BY_HOUR,
    GOLD_REVENUE_BY_ZONE_TODAY,
    GOLD_REVENUE_TREND,
    GOLD_TOP_REVENUE_ZONES,
    GOLD_TRIP_COUNT_TODAY,
)
from ..datasets.map_datasets import REVENUE_LOCATION_MAP

# Dataset tuple for this specific dashboard
# Include both consolidated and legacy datasets during transition
REVENUE_ANALYTICS_DATASETS = (
    # Consolidated datasets (with metrics)
    GOLD_PLATFORM_REVENUE,
    GOLD_PAYMENTS,
    # Legacy datasets (until charts are migrated)
    GOLD_DAILY_REVENUE,
    GOLD_PLATFORM_FEES,
    GOLD_TRIP_COUNT_TODAY,
    GOLD_REVENUE_BY_ZONE_TODAY,
    GOLD_REVENUE_TREND,
    GOLD_FARE_VS_DURATION,
    GOLD_PAYMENT_METHOD_MIX,
    GOLD_REVENUE_BY_HOUR,
    GOLD_TOP_REVENUE_ZONES,
    # Map dataset
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
