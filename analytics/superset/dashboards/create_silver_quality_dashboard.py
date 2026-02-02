#!/usr/bin/env python3
"""
Create Silver Quality Dashboard in Superset using virtual datasets.

This dashboard visualizes the Silver (data quality) layer of the medallion
lakehouse architecture. Charts show anomaly detection results, staging table
health, and data freshness.

Layout:
- Row 1: KPIs (Total Anomalies, GPS Outliers, Impossible Speeds) - width 4 each
- Row 2: Anomalies by Type, Anomalies Over Time - width 6 each
- Row 3: Staging Row Counts - width 12
- Row 4: Zombie Drivers, Data Freshness - width 6 each

Usage:
    # Standalone execution
    python3 create_silver_quality_dashboard.py

    # Called by orchestrator
    from create_silver_quality_dashboard import create_silver_quality_dashboard
    create_silver_quality_dashboard(client)
"""

import sys
from typing import Optional

from silver_queries import SILVER_QUALITY_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Silver Quality Dashboard"
DASHBOARD_SLUG = "silver-quality"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("silver_total_anomalies", "total_anomalies"),
    ("silver_gps_outliers_count", "gps_outliers_count"),
    ("silver_impossible_speeds_count", "impossible_speeds_count"),
    ("silver_anomalies_by_type", "anomalies_by_type"),
    ("silver_anomalies_over_time", "anomalies_over_time"),
    ("silver_staging_row_counts", "staging_row_counts"),
    ("silver_zombie_drivers_list", "zombie_drivers_list"),
    ("silver_staging_freshness", "staging_freshness"),
]

# Chart definitions: (chart_name, viz_type)
CHARTS = [
    ("Total Anomalies (24h)", "big_number_total"),
    ("GPS Outliers", "big_number_total"),
    ("Impossible Speeds", "big_number_total"),
    ("Anomalies by Type", "pie"),
    ("Anomalies Over Time", "echarts_timeseries_line"),
    ("Staging Row Counts", "dist_bar"),
    ("Zombie Drivers", "table"),
    ("Data Freshness", "table"),
]

# Layout configuration: (width, height) for each chart
LAYOUT = [
    (4, 3),  # Total Anomalies
    (4, 3),  # GPS Outliers
    (4, 3),  # Impossible Speeds
    (6, 4),  # Anomalies by Type
    (6, 4),  # Anomalies Over Time
    (12, 4),  # Staging Row Counts (full width)
    (6, 4),  # Zombie Drivers
    (6, 4),  # Staging Freshness
]


def create_silver_quality_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Silver Quality Dashboard.

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
        sql = SILVER_QUALITY_QUERIES[query_key]
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
        dashboard_id = create_silver_quality_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
