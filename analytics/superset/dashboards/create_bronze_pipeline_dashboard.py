#!/usr/bin/env python3
"""
Create Bronze Pipeline Dashboard in Superset using virtual datasets.

This dashboard visualizes the Bronze (raw ingestion) layer of the medallion
lakehouse architecture. Charts show ingestion metrics, DLQ errors, and data freshness.

Layout:
- Row 1: KPIs (Total Events, DLQ Errors, Ingestion Lag) - width 4 each
- Row 2: Events by Topic, Partition Distribution - width 6 each
- Row 3: Ingestion Rate - width 12
- Row 4: DLQ Errors by Type, Latest Ingestion - width 6 each

Usage:
    # Standalone execution
    python3 create_bronze_pipeline_dashboard.py

    # Called by orchestrator
    from create_bronze_pipeline_dashboard import create_bronze_pipeline_dashboard
    create_bronze_pipeline_dashboard(client)
"""

import sys
from typing import Optional

from bronze_queries import BRONZE_PIPELINE_QUERIES
from superset_client import SupersetClient


# Dashboard configuration
DASHBOARD_TITLE = "Bronze Pipeline Dashboard"
DASHBOARD_SLUG = "bronze-pipeline"
REFRESH_FREQUENCY = 300  # 5 minutes

# Dataset definitions: (table_name, query_key)
DATASETS = [
    ("bronze_total_events_24h", "total_events_24h"),
    ("bronze_dlq_error_count", "dlq_error_count"),
    ("bronze_ingestion_lag", "ingestion_lag"),
    ("bronze_events_by_topic", "events_by_topic"),
    ("bronze_partition_distribution", "partition_distribution"),
    ("bronze_ingestion_rate_hourly", "ingestion_rate_hourly"),
    ("bronze_dlq_errors_by_type", "dlq_errors_by_type"),
    ("bronze_latest_ingestion", "latest_ingestion"),
]

# Chart definitions: (chart_name, viz_type)
CHARTS = [
    ("Total Events (24h)", "big_number_total"),
    ("DLQ Errors", "big_number_total"),
    ("Max Ingestion Lag (s)", "big_number_total"),
    ("Events by Topic", "dist_bar"),
    ("Partition Distribution", "dist_bar"),
    ("Ingestion Rate (Hourly)", "echarts_timeseries_line"),
    ("DLQ Errors by Type", "pie"),
    ("Latest Ingestion", "table"),
]

# Layout configuration: (width, height) for each chart
LAYOUT = [
    (4, 3),  # Total Events 24h
    (4, 3),  # DLQ Errors
    (4, 3),  # Ingestion Lag
    (6, 4),  # Events by Topic
    (6, 4),  # Partition Distribution
    (12, 4),  # Ingestion Rate (full width)
    (6, 4),  # DLQ Errors by Type
    (6, 4),  # Latest Ingestion
]


def create_bronze_pipeline_dashboard(client: SupersetClient) -> Optional[int]:
    """Create the Bronze Pipeline Dashboard.

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
        sql = BRONZE_PIPELINE_QUERIES[query_key]
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
        dashboard_id = create_bronze_pipeline_dashboard(client)
        print(f"\nDashboard created successfully (ID: {dashboard_id})")
        print(f"URL: http://localhost:8088/superset/dashboard/{DASHBOARD_SLUG}/")
        return 0
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
