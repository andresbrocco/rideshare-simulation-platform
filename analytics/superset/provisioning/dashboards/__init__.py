"""Dashboard definitions for Superset provisioning.

This module exports all dashboard definitions.
"""

from .data_ingestion import DATA_INGESTION_DASHBOARD
from .data_quality import DATA_QUALITY_DASHBOARD
from .demand_analysis import DEMAND_ANALYSIS_DASHBOARD
from .driver_performance import DRIVER_PERFORMANCE_DASHBOARD
from .platform_operations import PLATFORM_OPERATIONS_DASHBOARD
from .revenue_analytics import REVENUE_ANALYTICS_DASHBOARD

__all__ = [
    "DATA_INGESTION_DASHBOARD",
    "DATA_QUALITY_DASHBOARD",
    "PLATFORM_OPERATIONS_DASHBOARD",
    "DRIVER_PERFORMANCE_DASHBOARD",
    "DEMAND_ANALYSIS_DASHBOARD",
    "REVENUE_ANALYTICS_DASHBOARD",
]

# All dashboards tuple for bulk provisioning
ALL_DASHBOARDS = (
    DATA_INGESTION_DASHBOARD,
    DATA_QUALITY_DASHBOARD,
    PLATFORM_OPERATIONS_DASHBOARD,
    DRIVER_PERFORMANCE_DASHBOARD,
    DEMAND_ANALYSIS_DASHBOARD,
    REVENUE_ANALYTICS_DASHBOARD,
)
