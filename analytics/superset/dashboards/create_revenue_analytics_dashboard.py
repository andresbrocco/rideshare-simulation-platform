#!/usr/bin/env python3
"""
Create Revenue Analytics Dashboard in Superset.

Charts:
1. Daily Revenue (Big Number with Trend)
2. Total Fees (Big Number)
3. Trip Count (Big Number)
4. Revenue by Zone (Bar Chart)
5. Revenue Over Time (Time Series Line)
6. Average Fare by Distance (Scatter Plot)
7. Payment Method Distribution (Pie Chart)
8. Revenue by Hour (Heatmap)
9. Top Revenue Zones (Table)

Usage:
    # Standalone execution
    python3 create_revenue_analytics_dashboard.py

    # Called by orchestrator
    from create_revenue_analytics_dashboard import create_revenue_analytics_dashboard
    create_revenue_analytics_dashboard(client)
"""

import sys
from typing import Any, Optional

from gold_queries import REVENUE_ANALYTICS_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Revenue Analytics Dashboard"
DASHBOARD_SLUG = "revenue-analytics"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("daily_revenue", "daily_revenue"),
    ("total_fees", "total_fees"),
    ("trip_count_kpi", "trip_count_kpi"),
    ("revenue_by_zone", "revenue_by_zone"),
    ("revenue_over_time", "revenue_over_time"),
    ("fare_by_distance", "fare_by_distance"),
    ("payment_methods", "payment_methods"),
    ("revenue_by_hour", "revenue_by_hour"),
    ("top_revenue_zones", "top_revenue_zones"),
]

# Chart definitions: (chart_name, viz_type, params)
CHARTS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "Daily Revenue",
        "big_number_total",
        {"viz_type": "big_number_total", "metrics": ["revenue"]},
    ),
    (
        "Total Fees",
        "big_number_total",
        {"viz_type": "big_number_total", "metrics": ["fees"]},
    ),
    (
        "Trip Count",
        "big_number_total",
        {"viz_type": "big_number_total", "metrics": ["count"]},
    ),
    (
        "Revenue by Zone",
        "dist_bar",
        {"viz_type": "dist_bar", "metrics": ["revenue"], "groupby": ["zone_id"]},
    ),
    (
        "Revenue Over Time",
        "echarts_timeseries_line",
        {"viz_type": "echarts_timeseries_line", "metrics": ["revenue"], "x_axis": "date"},
    ),
    (
        "Average Fare by Distance",
        "scatter",
        {"viz_type": "scatter", "x": "distance_km", "y": "fare"},
    ),
    (
        "Payment Method Distribution",
        "pie",
        {"viz_type": "pie", "metrics": ["count"], "groupby": ["method"]},
    ),
    (
        "Revenue by Hour",
        "heatmap",
        {"viz_type": "heatmap", "metrics": ["revenue"], "groupby": ["hour", "date"]},
    ),
    (
        "Top Revenue Zones",
        "table",
        {
            "viz_type": "table",
            "metrics": ["total_revenue"],
            "groupby": ["zone_id", "zone_name"],
            "row_limit": 10,
        },
    ),
]

# Layout configuration: (width, height) for each chart
# KPIs on top row (4 each), analytics charts below (6 each)
LAYOUT = [
    (4, 4),  # Daily Revenue
    (4, 4),  # Total Fees
    (4, 4),  # Trip Count
    (6, 8),  # Revenue by Zone
    (6, 8),  # Revenue Over Time
    (6, 8),  # Average Fare by Distance
    (6, 8),  # Payment Method Distribution
    (6, 8),  # Revenue by Hour
    (6, 8),  # Top Revenue Zones
]


def create_revenue_analytics_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Revenue Analytics Dashboard.

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
        sql = REVENUE_ANALYTICS_QUERIES[query_key]
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
        dashboard_id = create_revenue_analytics_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
