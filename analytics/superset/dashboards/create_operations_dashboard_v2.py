#!/usr/bin/env python3
"""
Create Operations Dashboard in Superset using virtual datasets.

This creates a minimal dashboard structure with real-time platform monitoring.
Charts use SQL queries as virtual datasets from the Gold layer.

Usage:
    # Standalone execution
    python3 create_operations_dashboard_v2.py

    # Called by orchestrator
    from create_operations_dashboard_v2 import create_operations_dashboard
    create_operations_dashboard(client)
"""

import sys
from typing import Optional

from gold_queries import OPERATIONS_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Operations Dashboard"
DASHBOARD_SLUG = "operations"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("active_trips", "active_trips"),
    ("completed_today", "completed_today"),
    ("avg_wait_time", "avg_wait_time"),
    ("total_revenue", "total_revenue"),
    ("dlq_errors_hourly", "dlq_errors_hourly"),
    ("dlq_errors_by_type", "dlq_errors_by_type"),
    ("hourly_trips", "hourly_trips"),
    ("pipeline_lag", "pipeline_lag"),
    ("trips_by_zone", "trips_by_zone"),
]

# Chart definitions: (chart_name, viz_type)
CHARTS = [
    ("Active Trips", "big_number_total"),
    ("Completed Today", "big_number_total"),
    ("Average Wait Time Today", "big_number_total"),
    ("Total Revenue Today", "big_number_total"),
    ("DLQ Errors Last Hour", "echarts_timeseries_bar"),
    ("Total DLQ Errors", "pie"),
    ("Hourly Trip Volume", "echarts_timeseries_line"),
    ("Pipeline Lag", "big_number_total"),
    ("Trips by Zone Today", "deck_polygon"),
]

# Layout configuration: (width, height) for each chart
LAYOUT = [
    (4, 4),  # Active Trips
    (4, 4),  # Completed Today
    (4, 4),  # Average Wait Time Today
    (4, 4),  # Total Revenue Today
    (4, 4),  # DLQ Errors Last Hour
    (4, 4),  # Total DLQ Errors
    (4, 4),  # Hourly Trip Volume
    (4, 4),  # Pipeline Lag
    (4, 4),  # Trips by Zone Today
]


def create_operations_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Operations Dashboard.

    Args:
        client: Authenticated SupersetClient instance

    Returns:
        Dashboard ID if created successfully, None otherwise

    Raises:
        Exception: If dashboard creation fails
    """
    # Get database ID
    database_id = client.get_database_id()
    if database_id is None:
        raise Exception("Database 'Rideshare Lakehouse' not found")

    print(f"Using database ID: {database_id}")

    # Create datasets
    dataset_ids = []
    for table_name, query_key in DATASETS:
        sql = OPERATIONS_QUERIES[query_key]
        dataset_id = client.get_or_create_dataset(database_id, table_name, sql)
        dataset_ids.append(dataset_id)

    # Create charts
    chart_ids = []
    for i, (chart_name, viz_type) in enumerate(CHARTS):
        chart_id = client.get_or_create_chart(dataset_ids[i], chart_name, viz_type)
        chart_ids.append(chart_id)

    # Create dashboard
    dashboard_id = client.get_or_create_dashboard(
        DASHBOARD_TITLE, DASHBOARD_SLUG, REFRESH_FREQUENCY
    )

    # Update dashboard with charts and layout
    client.update_dashboard(dashboard_id, chart_ids, LAYOUT, REFRESH_FREQUENCY)
    print("Updated dashboard metadata and layout")

    # Associate charts with dashboard
    client.associate_charts_with_dashboard(dashboard_id, chart_ids)
    print(f"Associated {len(chart_ids)} charts with dashboard")

    return dashboard_id


def main() -> int:
    """Main entry point for standalone execution.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    client = SupersetClient()
    if not client.authenticate():
        print("Failed to authenticate with Superset")
        return 1

    try:
        dashboard_id = create_operations_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
