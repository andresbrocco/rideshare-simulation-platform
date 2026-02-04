"""Platform Operations dashboard definition.

This dashboard provides real-time operational health and performance monitoring
for the rideshare platform using Gold and Silver layer data.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.map_charts import PLATFORM_OPERATIONS_MAP_CHARTS
from ..charts.platform_operations_charts import PLATFORM_OPERATIONS_CHARTS
from ..datasets.gold_datasets import (
    # Consolidated datasets
    GOLD_FACT_TRIPS,
    # Legacy datasets (for charts not yet migrated)
    OPS_AVG_WAIT_TIME,
    OPS_COMPLETED_TRIPS_TODAY,
    OPS_HOURLY_TRIP_VOLUME,
    OPS_HOURLY_ZONE_HEATMAP,
    OPS_PROCESSING_DELAY,
    OPS_ZONE_ACTIVITY_TODAY,
)
from ..datasets.map_datasets import (
    OPS_ACTIVE_TRIP_LOCATIONS,
    OPS_DRIVER_LOCATIONS,
)
from ..datasets.silver_datasets import (
    # Consolidated datasets
    SILVER_ACTIVE_TRIPS,
    SILVER_ANOMALIES,
    # Legacy datasets (for charts not yet migrated)
    OPS_ACTIVE_TRIPS,
    OPS_ERRORS_BY_CATEGORY,
    OPS_RECENT_ERRORS,
)

# Dataset tuple for this specific dashboard
# Include both consolidated and legacy datasets during transition
PLATFORM_OPERATIONS_DATASETS = (
    # Consolidated datasets (with metrics)
    SILVER_ACTIVE_TRIPS,
    SILVER_ANOMALIES,
    GOLD_FACT_TRIPS,
    # Legacy Silver layer datasets (until charts are migrated)
    OPS_ACTIVE_TRIPS,
    OPS_RECENT_ERRORS,
    OPS_ERRORS_BY_CATEGORY,
    # Legacy Gold layer datasets (until charts are migrated)
    OPS_COMPLETED_TRIPS_TODAY,
    OPS_AVG_WAIT_TIME,
    OPS_HOURLY_TRIP_VOLUME,
    OPS_PROCESSING_DELAY,
    OPS_ZONE_ACTIVITY_TODAY,
    OPS_HOURLY_ZONE_HEATMAP,
    # Map datasets
    OPS_DRIVER_LOCATIONS,
    OPS_ACTIVE_TRIP_LOCATIONS,
)

# Combine standard charts with map charts
PLATFORM_OPERATIONS_ALL_CHARTS = PLATFORM_OPERATIONS_CHARTS + PLATFORM_OPERATIONS_MAP_CHARTS

PLATFORM_OPERATIONS_DASHBOARD = DashboardDefinition(
    title="Platform Operations",
    slug="platform-operations",
    description=(
        "Real-time operational health and performance monitoring for the "
        "rideshare platform. Answers: Is the platform healthy? What's "
        "happening right now?"
    ),
    datasets=PLATFORM_OPERATIONS_DATASETS,
    charts=PLATFORM_OPERATIONS_ALL_CHARTS,
    required_tables=(
        "gold.fact_trips",
        "gold.fact_payments",
        "gold.agg_hourly_zone_demand",
        "gold.dim_zones",
        "gold.dim_time",
        "silver.stg_trips",
        "silver.stg_driver_status",
        "silver.anomalies_all",
    ),
    refresh_interval=60,
)
