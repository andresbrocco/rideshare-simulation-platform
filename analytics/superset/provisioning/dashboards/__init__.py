"""Dashboard definitions for all data layers."""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)
from provisioning.dashboards.data_ingestion import DATA_INGESTION_DASHBOARD
from provisioning.dashboards.data_quality import DATA_QUALITY_DASHBOARD
from provisioning.dashboards.demand_analysis import DEMAND_ANALYSIS_DASHBOARD
from provisioning.dashboards.driver_performance import DRIVER_PERFORMANCE_DASHBOARD
from provisioning.dashboards.platform_operations import PLATFORM_OPERATIONS_DASHBOARD
from provisioning.dashboards.revenue_analytics import REVENUE_ANALYTICS_DASHBOARD

ALL_DASHBOARDS: tuple[DashboardDefinition, ...] = (
    DATA_INGESTION_DASHBOARD,
    DATA_QUALITY_DASHBOARD,
    PLATFORM_OPERATIONS_DASHBOARD,
    DRIVER_PERFORMANCE_DASHBOARD,
    DEMAND_ANALYSIS_DASHBOARD,
    REVENUE_ANALYTICS_DASHBOARD,
)

__all__ = [
    "DatasetDefinition",
    "ChartDefinition",
    "DashboardDefinition",
    "DATA_INGESTION_DASHBOARD",
    "DATA_QUALITY_DASHBOARD",
    "PLATFORM_OPERATIONS_DASHBOARD",
    "DRIVER_PERFORMANCE_DASHBOARD",
    "DEMAND_ANALYSIS_DASHBOARD",
    "REVENUE_ANALYTICS_DASHBOARD",
    "ALL_DASHBOARDS",
]
