#!/usr/bin/env python3
"""
Create Driver Performance Dashboard in Superset.

Charts:
1. Top 10 Drivers by Trips (Bar Chart)
2. Driver Ratings Distribution (Histogram)
3. Driver Payouts Over Time (Time Series Line)
4. Driver Utilization Heatmap (Heatmap)
5. Trips per Driver (Scatter Plot)
6. Driver Status Summary (Pie Chart)

Usage:
    # Standalone execution
    python3 create_driver_performance_dashboard.py

    # Called by orchestrator
    from create_driver_performance_dashboard import create_driver_performance_dashboard
    create_driver_performance_dashboard(client)
"""

import sys
from typing import Any, Optional

from gold_queries import DRIVER_PERFORMANCE_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Driver Performance Dashboard"
DASHBOARD_SLUG = "driver-performance"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("top_drivers", "top_drivers"),
    ("driver_ratings", "driver_ratings"),
    ("driver_payouts", "driver_payouts"),
    ("driver_utilization", "driver_utilization"),
    ("trips_per_driver", "trips_per_driver"),
    ("driver_status", "driver_status"),
]

# Chart definitions: (chart_name, viz_type, params)
CHARTS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "Top 10 Drivers by Trips",
        "dist_bar",
        {
            "viz_type": "dist_bar",
            "metrics": ["trip_count"],
            "groupby": ["driver_name"],
            "row_limit": 10,
        },
    ),
    (
        "Driver Ratings Distribution",
        "histogram",
        {"viz_type": "histogram", "metrics": ["driver_count"], "column": "rating"},
    ),
    (
        "Driver Payouts Over Time",
        "echarts_timeseries_line",
        {"viz_type": "echarts_timeseries_line", "metrics": ["payout"], "x_axis": "date"},
    ),
    (
        "Driver Utilization Heatmap",
        "heatmap",
        {"viz_type": "heatmap", "metrics": ["utilization"], "groupby": ["driver_id", "date"]},
    ),
    (
        "Trips per Driver",
        "scatter",
        {"viz_type": "scatter", "x": "trips", "y": "revenue", "entity": "driver_id"},
    ),
    (
        "Driver Status Summary",
        "pie",
        {"viz_type": "pie", "metrics": ["count"], "groupby": ["status"]},
    ),
]

# Layout configuration: (width, height) for each chart
LAYOUT = [
    (6, 8),  # Top 10 Drivers by Trips
    (6, 8),  # Driver Ratings Distribution
    (6, 8),  # Driver Payouts Over Time
    (6, 8),  # Driver Utilization Heatmap
    (6, 8),  # Trips per Driver
    (6, 8),  # Driver Status Summary
]


def create_driver_performance_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Driver Performance Dashboard.

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
        sql = DRIVER_PERFORMANCE_QUERIES[query_key]
        dataset_id = client.get_or_create_dataset(database_id, table_name, sql)
        dataset_ids.append(dataset_id)

    # Create charts
    chart_ids = []
    for i, (chart_name, viz_type, params) in enumerate(CHARTS):
        chart_id = client.get_or_create_chart(dataset_ids[i], chart_name, viz_type, params)
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
        dashboard_id = create_driver_performance_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
