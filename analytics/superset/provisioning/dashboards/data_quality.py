"""Data Quality Monitoring dashboard definition.

This dashboard monitors data validation and quality metrics across
Silver layer staging tables, tracking anomalies and data integrity.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.data_quality_charts import DATA_QUALITY_CHARTS
from ..charts.map_charts import DATA_QUALITY_MAP_CHARTS
from ..datasets.map_datasets import DQ_GPS_ANOMALY_LOCATIONS
from ..datasets.silver_datasets import (
    SILVER_ANOMALIES,
    SILVER_STAGING_HEALTH,
    SILVER_STALE_DRIVERS,
)

# Dataset tuple for this specific dashboard - consolidated datasets only
DATA_QUALITY_DATASETS = (
    SILVER_ANOMALIES,
    SILVER_STAGING_HEALTH,
    SILVER_STALE_DRIVERS,
    DQ_GPS_ANOMALY_LOCATIONS,
)

# Combine standard charts with map charts
DATA_QUALITY_ALL_CHARTS = DATA_QUALITY_CHARTS + DATA_QUALITY_MAP_CHARTS

DATA_QUALITY_DASHBOARD = DashboardDefinition(
    title="Data Quality Monitoring",
    slug="data-quality-monitoring",
    description=(
        "Monitor data validation and quality metrics across Silver layer "
        "staging tables. Tracks anomalies including GPS outliers, impossible "
        "speeds, and zombie drivers to ensure data integrity before analytics "
        "consumption."
    ),
    datasets=DATA_QUALITY_DATASETS,
    charts=DATA_QUALITY_ALL_CHARTS,
    required_tables=(
        "silver.stg_trips",
        "silver.stg_gps_pings",
        "silver.stg_driver_status",
        "silver.stg_surge_updates",
        "silver.stg_ratings",
        "silver.stg_payments",
        "silver.stg_drivers",
        "silver.stg_riders",
        "silver.anomalies_all",
        "silver.anomalies_gps_outliers",
        "silver.anomalies_impossible_speeds",
        "silver.anomalies_zombie_drivers",
    ),
    refresh_interval=300,
)
