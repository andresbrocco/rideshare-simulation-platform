#!/usr/bin/env python3
"""
Create Demand Analysis Dashboard in Superset.

Charts:
1. Zone Demand Heatmap (Heatmap)
2. Surge Multiplier Trends (Time Series Line)
3. Average Wait Time by Zone (Bar Chart)
4. Demand by Hour of Day (Area Chart)
5. Top Demand Zones (Table)
6. Surge Events Timeline (Time Series Bar)

Usage:
    # Standalone execution
    python3 create_demand_analysis_dashboard.py

    # Called by orchestrator
    from create_demand_analysis_dashboard import create_demand_analysis_dashboard
    create_demand_analysis_dashboard(client)
"""

import sys
from typing import Any, Optional

from gold_queries import DEMAND_ANALYSIS_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Demand Analysis Dashboard"
DASHBOARD_SLUG = "demand-analysis"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("zone_demand_heatmap", "zone_demand_heatmap"),
    ("surge_trends", "surge_trends"),
    ("wait_time_by_zone", "wait_time_by_zone"),
    ("demand_by_hour", "demand_by_hour"),
    ("top_demand_zones", "top_demand_zones"),
    ("surge_events", "surge_events"),
]

# Chart definitions: (chart_name, viz_type, params)
CHARTS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "Zone Demand Heatmap",
        "heatmap",
        {"viz_type": "heatmap", "metrics": ["demand"], "groupby": ["zone_id", "date"]},
    ),
    (
        "Surge Multiplier Trends",
        "echarts_timeseries_line",
        {
            "viz_type": "echarts_timeseries_line",
            "metrics": ["surge_multiplier"],
            "x_axis": "timestamp",
        },
    ),
    (
        "Average Wait Time by Zone",
        "dist_bar",
        {"viz_type": "dist_bar", "metrics": ["avg_wait_minutes"], "groupby": ["zone_id"]},
    ),
    (
        "Demand by Hour of Day",
        "echarts_area",
        {"viz_type": "echarts_area", "metrics": ["request_count"], "x_axis": "hour_of_day"},
    ),
    (
        "Top Demand Zones",
        "table",
        {
            "viz_type": "table",
            "metrics": ["total_requests"],
            "groupby": ["zone_id", "zone_name"],
            "row_limit": 10,
        },
    ),
    (
        "Surge Events Timeline",
        "echarts_timeseries_bar",
        {"viz_type": "echarts_timeseries_bar", "metrics": ["multiplier"], "x_axis": "timestamp"},
    ),
]

# Layout configuration: (width, height) for each chart
LAYOUT = [
    (6, 8),  # Zone Demand Heatmap
    (6, 8),  # Surge Multiplier Trends
    (6, 8),  # Average Wait Time by Zone
    (6, 8),  # Demand by Hour of Day
    (6, 8),  # Top Demand Zones
    (6, 8),  # Surge Events Timeline
]


def create_demand_analysis_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Demand Analysis Dashboard.

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
        sql = DEMAND_ANALYSIS_QUERIES[query_key]
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
        dashboard_id = create_demand_analysis_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
