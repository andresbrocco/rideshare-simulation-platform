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
"""

import requests
import json
import sys


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
                raise Exception(f"Failed to associate chart {chart_id}: {response.text}")

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
            "table_name": "zone_demand_heatmap",
            "sql": "SELECT 'zone_123' as zone_id, '2026-01-17' as date, 150 as demand",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "surge_trends",
            "sql": "SELECT NOW() as timestamp, 1.5 as surge_multiplier",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "wait_time_by_zone",
            "sql": "SELECT 'zone_123' as zone_id, 3.5 as avg_wait_minutes",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "demand_by_hour",
            "sql": "SELECT 14 as hour_of_day, 85 as request_count",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "top_demand_zones",
            "sql": "SELECT 'zone_123' as zone_id, 'Downtown' as zone_name, 450 as total_requests",
        },
        {
            "database": database_id,
            "schema": "",
            "table_name": "surge_events",
            "sql": "SELECT NOW() as timestamp, 'zone_123' as zone_id, 2.0 as multiplier",
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
                    found = False
                    for existing_ds in all_datasets:
                        if existing_ds.get("table_name") == ds["table_name"]:
                            ds_id = existing_ds.get("id")
                            dataset_ids.append(ds_id)
                            print(f"Using existing dataset: {ds['table_name']} (ID: {ds_id})")
                            found = True
                            break
                    if not found:
                        print(f"Warning: Dataset {ds['table_name']} exists but not found in list")
            else:
                print(f"Warning: {e}")

    if len(dataset_ids) < 6:
        print(f"Error: Only created {len(dataset_ids)} of 6 datasets")
        sys.exit(1)

    charts_config = [
        {
            "slice_name": "Zone Demand Heatmap",
            "viz_type": "heatmap",
            "datasource_id": dataset_ids[0],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "heatmap",
                    "metrics": ["demand"],
                    "groupby": ["zone_id", "date"],
                }
            ),
        },
        {
            "slice_name": "Surge Multiplier Trends",
            "viz_type": "echarts_timeseries_line",
            "datasource_id": dataset_ids[1],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_timeseries_line",
                    "metrics": ["surge_multiplier"],
                    "x_axis": "timestamp",
                }
            ),
        },
        {
            "slice_name": "Average Wait Time by Zone",
            "viz_type": "dist_bar",
            "datasource_id": dataset_ids[2],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "dist_bar",
                    "metrics": ["avg_wait_minutes"],
                    "groupby": ["zone_id"],
                }
            ),
        },
        {
            "slice_name": "Demand by Hour of Day",
            "viz_type": "echarts_area",
            "datasource_id": dataset_ids[3],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_area",
                    "metrics": ["request_count"],
                    "x_axis": "hour_of_day",
                }
            ),
        },
        {
            "slice_name": "Top Demand Zones",
            "viz_type": "table",
            "datasource_id": dataset_ids[4],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "table",
                    "metrics": ["total_requests"],
                    "groupby": ["zone_id", "zone_name"],
                    "row_limit": 10,
                }
            ),
        },
        {
            "slice_name": "Surge Events Timeline",
            "viz_type": "echarts_timeseries_bar",
            "datasource_id": dataset_ids[5],
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_timeseries_bar",
                    "metrics": ["multiplier"],
                    "x_axis": "timestamp",
                }
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
        print(f"Error: Only created {len(chart_ids)} of 6 charts")
        sys.exit(1)

    dashboard_id = client.create_dashboard("Demand Analysis Dashboard", "demand-analysis")
    print(f"Created dashboard: Demand Analysis Dashboard (ID: {dashboard_id})")

    client.update_dashboard(dashboard_id, chart_ids)
    print("Updated dashboard with charts")

    client.associate_charts(dashboard_id, chart_ids)
    print("Associated charts with dashboard")

    output_file = "demand-analysis-export.zip"
    client.export_dashboard(dashboard_id, output_file)
    print(f"Exported dashboard to {output_file}")


if __name__ == "__main__":
    main()
