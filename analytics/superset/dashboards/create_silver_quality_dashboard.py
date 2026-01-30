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
"""

import json
import sys

import requests

from silver_queries import SILVER_QUALITY_QUERIES

# Database name must match what docker-entrypoint.sh creates
DATABASE_NAME = "Rideshare Lakehouse"


class SupersetClient:
    def __init__(self, base_url="http://localhost:8088", username="admin", password="admin"):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(username, password)
        self._get_csrf_token()

    def _login(self, username, password):
        login_url = f"{self.base_url}/api/v1/security/login"
        login_data = {
            "username": username,
            "password": password,
            "provider": "db",
            "refresh": True,
        }
        response = self.session.post(login_url, json=login_data)
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text}")

        token_data = response.json()
        access_token = token_data.get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})

    def _get_csrf_token(self):
        csrf_url = f"{self.base_url}/api/v1/security/csrf_token/"
        csrf_response = self.session.get(csrf_url)
        if csrf_response.status_code != 200:
            raise Exception(f"Failed to get CSRF token: {csrf_response.text}")

        csrf_token = csrf_response.json().get("result")
        self.session.headers.update(
            {
                "X-CSRFToken": csrf_token,
                "Referer": self.base_url,
                "Content-Type": "application/json",
            }
        )

    def get_database(self):
        # Get Rideshare Lakehouse database
        list_url = f"{self.base_url}/api/v1/database/"
        response = self.session.get(list_url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch databases: {response.text}")

        databases = response.json().get("result", [])

        # Look for Rideshare Lakehouse (created by docker-entrypoint.sh)
        for db in databases:
            db_name = db.get("database_name", "")
            if db_name == DATABASE_NAME:
                return db.get("id")

        raise Exception(
            f"Database '{DATABASE_NAME}' not found. Ensure Superset container started correctly."
        )

    def create_dataset(self, database_id, table_name, sql):
        """Create a virtual dataset from SQL query."""
        dataset_config = {
            "database": database_id,
            "schema": "",
            "table_name": table_name,
            "sql": sql,
            "owners": [],
        }

        url = f"{self.base_url}/api/v1/dataset/"
        response = self.session.post(url, json=dataset_config)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create dataset {table_name}: {response.text}")

    def create_chart(self, dataset_id, slice_name, viz_type):
        """Create a simple chart."""
        chart_config = {
            "slice_name": slice_name,
            "viz_type": viz_type,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps({"viz_type": viz_type, "metrics": ["count"], "adhoc_filters": []}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": dataset_id, "type": "table"},
                    "force": False,
                    "queries": [{"metrics": ["count"], "filters": []}],
                    "result_format": "json",
                    "result_type": "full",
                }
            ),
        }

        url = f"{self.base_url}/api/v1/chart/"
        response = self.session.post(url, json=chart_config)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create chart {slice_name}: {response.text}")

    def create_dashboard(self, title, slug, refresh_frequency=300):
        """Create empty dashboard."""
        dashboard_config = {"dashboard_title": title, "slug": slug, "published": True}

        url = f"{self.base_url}/api/v1/dashboard/"
        response = self.session.post(url, json=dashboard_config)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create dashboard: {response.text}")

    def update_dashboard(self, dashboard_id, chart_ids, refresh_frequency=300):
        """Update dashboard with charts and metadata."""
        position_json = {
            "DASHBOARD_VERSION_KEY": "v2",
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [],
                "parents": ["ROOT_ID"],
            },
        }

        # Layout configuration: (width, height) for each chart
        # Row 1: KPIs (3 charts, width 4 each)
        # Row 2: 2 charts, width 6 each
        # Row 3: 1 chart, width 12
        # Row 4: 2 charts, width 6 each
        layout = [
            (4, 3),  # Total Anomalies
            (4, 3),  # GPS Outliers
            (4, 3),  # Impossible Speeds
            (6, 4),  # Anomalies by Type
            (6, 4),  # Anomalies Over Time
            (12, 4),  # Staging Row Counts (full width)
            (6, 4),  # Zombie Drivers
            (6, 4),  # Staging Freshness
        ]

        # Add charts to position
        for i, chart_id in enumerate(chart_ids):
            chart_key = f"CHART-{i}"
            position_json["GRID_ID"]["children"].append(chart_key)  # type: ignore[index]
            width, height = layout[i] if i < len(layout) else (4, 4)
            position_json[chart_key] = {
                "type": "CHART",
                "id": chart_key,
                "children": [],
                "parents": ["GRID_ID"],
                "meta": {"width": width, "height": height, "chartId": chart_id},
            }

        update_config = {
            "position_json": json.dumps(position_json),
            "json_metadata": json.dumps(
                {
                    "refresh_frequency": refresh_frequency,
                    "color_scheme": "supersetColors",
                }
            ),
        }

        url = f"{self.base_url}/api/v1/dashboard/{dashboard_id}"
        response = self.session.put(url, json=update_config)

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to update dashboard: {response.text}")

    def associate_charts_with_dashboard(self, dashboard_id, chart_ids):
        """Associate charts with dashboard by updating each chart."""
        for chart_id in chart_ids:
            chart_url = f"{self.base_url}/api/v1/chart/{chart_id}"
            update_data = {"dashboards": [dashboard_id]}

            response = self.session.put(chart_url, json=update_data)
            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to associate chart {chart_id}: {response.text}")

    def export_dashboard(self, dashboard_id, output_path):
        """Export dashboard to JSON file."""
        url = f"{self.base_url}/api/v1/dashboard/export/"
        params = {"q": json.dumps([dashboard_id])}
        response = self.session.get(url, params=params)

        if response.status_code != 200:
            raise Exception(f"Failed to export dashboard: {response.text}")

        with open(output_path, "wb") as f:
            f.write(response.content)


def main():
    client = SupersetClient()

    # Get database
    database_id = client.get_database()
    print(f"Using database ID: {database_id}")

    # Create virtual datasets using Silver layer queries
    datasets = [
        ("silver_total_anomalies", SILVER_QUALITY_QUERIES["total_anomalies"]),
        ("silver_gps_outliers_count", SILVER_QUALITY_QUERIES["gps_outliers_count"]),
        ("silver_impossible_speeds_count", SILVER_QUALITY_QUERIES["impossible_speeds_count"]),
        ("silver_anomalies_by_type", SILVER_QUALITY_QUERIES["anomalies_by_type"]),
        ("silver_anomalies_over_time", SILVER_QUALITY_QUERIES["anomalies_over_time"]),
        ("silver_staging_row_counts", SILVER_QUALITY_QUERIES["staging_row_counts"]),
        ("silver_zombie_drivers_list", SILVER_QUALITY_QUERIES["zombie_drivers_list"]),
        ("silver_staging_freshness", SILVER_QUALITY_QUERIES["staging_freshness"]),
    ]

    dataset_ids = []
    for table_name, sql in datasets:
        try:
            dataset_id = client.create_dataset(database_id, table_name, sql)
            dataset_ids.append(dataset_id)
            print(f"Created dataset: {table_name} (ID: {dataset_id})")
        except Exception as e:
            print(f"Error creating dataset {table_name}: {e}")
            sys.exit(1)

    # Create charts
    chart_definitions = [
        ("Total Anomalies (24h)", "big_number_total"),
        ("GPS Outliers", "big_number_total"),
        ("Impossible Speeds", "big_number_total"),
        ("Anomalies by Type", "pie"),
        ("Anomalies Over Time", "echarts_timeseries_line"),
        ("Staging Row Counts", "dist_bar"),
        ("Zombie Drivers", "table"),
        ("Data Freshness", "table"),
    ]

    chart_ids = []
    for i, (chart_name, viz_type) in enumerate(chart_definitions):
        try:
            chart_id = client.create_chart(dataset_ids[i], chart_name, viz_type)
            chart_ids.append(chart_id)
            print(f"Created chart: {chart_name} (ID: {chart_id})")
        except Exception as e:
            print(f"Error creating chart {chart_name}: {e}")
            sys.exit(1)

    # Create dashboard
    try:
        dashboard_id = client.create_dashboard("Silver Quality Dashboard", "silver-quality")
        print(f"\nCreated dashboard: Silver Quality Dashboard (ID: {dashboard_id})")

        # Update dashboard with metadata and layout
        client.update_dashboard(dashboard_id, chart_ids, refresh_frequency=300)
        print("Updated dashboard metadata and layout")

        # Associate charts with dashboard
        client.associate_charts_with_dashboard(dashboard_id, chart_ids)
        print(f"Associated {len(chart_ids)} charts with dashboard")
        print("Dashboard URL: http://localhost:8088/superset/dashboard/silver-quality/")

        # Export dashboard
        output_path = "/app/dashboards/silver-quality.json"
        try:
            client.export_dashboard(dashboard_id, output_path)
            print(f"Dashboard exported to: {output_path}")
        except Exception as e:
            print(f"Warning: Could not export dashboard: {e}")

    except Exception as e:
        print(f"Error creating dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
