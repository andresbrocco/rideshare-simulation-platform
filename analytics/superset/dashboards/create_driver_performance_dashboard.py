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
"""

import requests
import json
import sys


class SupersetClient:
    def __init__(
        self, base_url="http://localhost:8088", username="admin", password="admin"
    ):
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

    def get_database_id(self, database_name="Rideshare Gold Layer"):
        url = f"{self.base_url}/api/v1/database/"
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch databases: {response.text}")

        databases = response.json().get("result", [])
        for db in databases:
            if db.get("database_name") == database_name:
                return db.get("id")
        raise Exception(f"Database '{database_name}' not found")

    def create_dataset(self, dataset_config):
        url = f"{self.base_url}/api/v1/dataset/"
        response = self.session.post(url, json=dataset_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create dataset: {response.text}")
        return response.json().get("id")

    def create_chart(self, chart_config):
        url = f"{self.base_url}/api/v1/chart/"
        response = self.session.post(url, json=chart_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create chart: {response.text}")
        return response.json().get("id")

    def create_dashboard(self, title, slug):
        dashboard_config = {"dashboard_title": title, "slug": slug, "published": True}
        url = f"{self.base_url}/api/v1/dashboard/"
        response = self.session.post(url, json=dashboard_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create dashboard: {response.text}")
        return response.json().get("id")

    def update_dashboard(self, dashboard_id, chart_ids):
        position_json = {
            "DASHBOARD_VERSION_KEY": "v2",
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [f"CHART-{i}" for i in range(len(chart_ids))],
                "parents": ["ROOT_ID"],
            },
        }

        for i, chart_id in enumerate(chart_ids):
            position_json[f"CHART-{i}"] = {
                "type": "CHART",
                "id": f"CHART-{i}",
                "children": [],
                "parents": ["GRID_ID"],
                "meta": {"width": 6, "height": 8, "chartId": chart_id},
            }

        update_config = {
            "position_json": json.dumps(position_json),
            "json_metadata": json.dumps({"refresh_frequency": 300}),
        }

        url = f"{self.base_url}/api/v1/dashboard/{dashboard_id}"
        response = self.session.put(url, json=update_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to update dashboard: {response.text}")

    def associate_charts(self, dashboard_id, chart_ids):
        for chart_id in chart_ids:
            chart_url = f"{self.base_url}/api/v1/chart/{chart_id}"
            update_data = {"dashboards": [dashboard_id]}
            response = self.session.put(chart_url, json=update_data)
            if response.status_code not in [200, 201]:
                raise Exception(
                    f"Failed to associate chart {chart_id}: {response.text}"
                )

    def export_dashboard(self, dashboard_id, output_file):
        url = f"{self.base_url}/api/v1/dashboard/export/"
        params = {"q": json.dumps([dashboard_id])}
        response = self.session.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to export dashboard: {response.text}")

        with open(output_file, "wb") as f:
            f.write(response.content)


def main():
    client = SupersetClient()
    database_id = client.get_database_id()
    print(f"Using database ID: {database_id}")

    datasets = [
        {
            "database": database_id,
            "schema": "",
            "table_name": "top_drivers",
            "sql": "SELECT 'driver_123' as driver_id, 'John Smith' as driver_name, 45 as trip_count",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "driver_ratings",
            "sql": "SELECT 4.8 as rating, 12 as driver_count",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "driver_payouts",
            "sql": "SELECT NOW() as date, 1250.50 as payout",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "driver_utilization",
            "sql": "SELECT 'driver_123' as driver_id, '2026-01-17' as date, 0.75 as utilization",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "trips_per_driver",
            "sql": "SELECT 'driver_123' as driver_id, 45 as trips, 320.5 as revenue",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "driver_status",
            "sql": "SELECT 'available' as status, 120 as count",
        },
    ]

    dataset_ids = []
    for ds in datasets:
        try:
            ds_id = client.create_dataset(ds)
            dataset_ids.append(ds_id)
            print(f"Created dataset: {ds['table_name']} (ID: {ds_id})")
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg:
                url = f"{client.base_url}/api/v1/dataset/?q=(page_size:100)"
                response = client.session.get(url)
                if response.status_code == 200:
                    all_datasets = response.json().get("result", [])
                    for existing_ds in all_datasets:
                        if existing_ds.get("table_name") == ds["table_name"]:
                            ds_id = existing_ds.get("id")
                            dataset_ids.append(ds_id)
                            print(
                                f"Using existing dataset: {ds['table_name']} (ID: {ds_id})"
                            )
                            break
            else:
                print(f"Warning: {e}")
                continue

    if len(dataset_ids) < 6:
        print(f"Error: Only created {len(dataset_ids)} of 6 datasets")
        sys.exit(1)

    charts_config = [
        {
            "slice_name": "Top 10 Drivers by Trips",
            "viz_type": "dist_bar",
            "datasource_id": dataset_ids[0],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "dist_bar",
                    "metrics": ["trip_count"],
                    "groupby": ["driver_name"],
                    "row_limit": 10,
                }
            ),
        },
        {
            "slice_name": "Driver Ratings Distribution",
            "viz_type": "histogram",
            "datasource_id": dataset_ids[1],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "histogram",
                    "metrics": ["driver_count"],
                    "column": "rating",
                }
            ),
        },
        {
            "slice_name": "Driver Payouts Over Time",
            "viz_type": "echarts_timeseries_line",
            "datasource_id": dataset_ids[2],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_timeseries_line",
                    "metrics": ["payout"],
                    "x_axis": "date",
                }
            ),
        },
        {
            "slice_name": "Driver Utilization Heatmap",
            "viz_type": "heatmap",
            "datasource_id": dataset_ids[3],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "heatmap",
                    "metrics": ["utilization"],
                    "groupby": ["driver_id", "date"],
                }
            ),
        },
        {
            "slice_name": "Trips per Driver",
            "viz_type": "scatter",
            "datasource_id": dataset_ids[4],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "scatter",
                    "x": "trips",
                    "y": "revenue",
                    "entity": "driver_id",
                }
            ),
        },
        {
            "slice_name": "Driver Status Summary",
            "viz_type": "pie",
            "datasource_id": dataset_ids[5],
            "datasource_type": "table",
            "params": json.dumps(
                {"viz_type": "pie", "metrics": ["count"], "groupby": ["status"]}
            ),
        },
    ]

    chart_ids = []
    for chart_cfg in charts_config:
        try:
            chart_id = client.create_chart(chart_cfg)
            chart_ids.append(chart_id)
            print(f"Created chart: {chart_cfg['slice_name']} (ID: {chart_id})")
        except Exception as e:
            print(f"Warning: {e}")
            continue

    if len(chart_ids) < 6:
        print("Error: Not all charts created")
        sys.exit(1)

    dashboard_id = client.create_dashboard(
        "Driver Performance Dashboard", "driver-performance"
    )
    print(f"Created dashboard: Driver Performance Dashboard (ID: {dashboard_id})")

    client.update_dashboard(dashboard_id, chart_ids)
    print("Updated dashboard with charts")

    client.associate_charts(dashboard_id, chart_ids)
    print("Associated charts with dashboard")

    output_file = "driver-performance-export.zip"
    client.export_dashboard(dashboard_id, output_file)
    print(f"Exported dashboard to {output_file}")


if __name__ == "__main__":
    main()
