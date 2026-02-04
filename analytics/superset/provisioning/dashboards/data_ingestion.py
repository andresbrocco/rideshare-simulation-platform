"""Data Ingestion Monitoring dashboard definition.

This dashboard monitors Bronze layer data pipeline health,
ingestion metrics, and error tracking.
"""

from provisioning.dashboards.base import DashboardDefinition

from ..charts.data_ingestion_charts import DATA_INGESTION_CHARTS
from ..datasets.bronze_datasets import BRONZE_DATASETS

DATA_INGESTION_DASHBOARD = DashboardDefinition(
    title="Data Ingestion Monitoring",
    slug="data-ingestion-monitoring",
    description=(
        "Monitor Bronze layer data pipeline health, ingestion metrics, " "and error tracking"
    ),
    datasets=BRONZE_DATASETS,
    charts=DATA_INGESTION_CHARTS,
    required_tables=(
        "bronze.bronze_trips",
        "bronze.bronze_gps_pings",
        "bronze.bronze_driver_status",
        "bronze.bronze_surge_updates",
        "bronze.bronze_ratings",
        "bronze.bronze_payments",
        "bronze.bronze_driver_profiles",
        "bronze.bronze_rider_profiles",
        "bronze.bronze_dlq",
    ),
    refresh_interval=300,
)
