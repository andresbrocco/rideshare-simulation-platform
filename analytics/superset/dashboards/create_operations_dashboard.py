#!/usr/bin/env python3
"""
Create Operations Dashboard in Superset programmatically.

This script creates a dashboard with 9 charts for operational monitoring:
- Trip metrics (active trips, completed today, wait time, revenue)
- DLQ error monitoring
- Pipeline health indicators
- Zone map visualization
"""

import requests
import json
import sys


class SupersetClient:
    def __init__(self, base_url="http://localhost:8088", username="admin", password="admin"):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(username, password)

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
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
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

    def create_chart(self, chart_config):
        url = f"{self.base_url}/api/v1/chart/"
        response = self.session.post(url, json=chart_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create chart: {response.text}")
        return response.json().get("id")

    def create_dashboard(self, dashboard_config):
        url = f"{self.base_url}/api/v1/dashboard/"
        response = self.session.post(url, json=dashboard_config)
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create dashboard: {response.text}")
        return response.json().get("id")

    def export_dashboard(self, dashboard_id):
        url = f"{self.base_url}/api/v1/dashboard/export/"
        params = {"q": json.dumps([dashboard_id])}
        response = self.session.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to export dashboard: {response.text}")
        return response.content


def create_operations_dashboard():
    client = SupersetClient()
    database_id = client.get_database_id()

    print(f"Found database with ID: {database_id}")

    # Chart configurations
    charts = [
        {
            "slice_name": "Active Trips",
            "viz_type": "big_number_total",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "metric": "count",
                    "adhoc_filters": [],
                    "viz_type": "big_number_total",
                    "header_font_size": 0.3,
                    "subheader_font_size": 0.15,
                }
            ),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "metrics": ["count"],
                            "filters": [],
                            "custom_sql": "SELECT COUNT(*) as count FROM gold.fact_trips WHERE trip_state = 'STARTED'",
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Completed Today",
            "viz_type": "big_number_total",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps({"metric": "count", "viz_type": "big_number_total"}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT COUNT(*) as count FROM gold.fact_trips WHERE DATE(dropoff_time) = CURRENT_DATE AND trip_state = 'COMPLETED'"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Average Wait Time Today",
            "viz_type": "big_number_total",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps({"metric": "avg_wait", "viz_type": "big_number_total"}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT AVG(wait_duration_minutes) as avg_wait FROM gold.fact_trips WHERE DATE(pickup_time) = CURRENT_DATE"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Total Revenue Today",
            "viz_type": "big_number_total",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps({"metric": "revenue", "viz_type": "big_number_total"}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT SUM(total_fare) as revenue FROM gold.fact_trips WHERE DATE(dropoff_time) = CURRENT_DATE"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "DLQ Errors Last Hour",
            "viz_type": "echarts_timeseries_bar",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_timeseries_bar",
                    "x_axis": "error_timestamp",
                    "metrics": ["count"],
                }
            ),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT DATE_TRUNC('minute', error_timestamp) as error_timestamp, COUNT(*) as count FROM bronze.dlq_errors WHERE error_timestamp >= NOW() - INTERVAL '1 hour' GROUP BY DATE_TRUNC('minute', error_timestamp)"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Total DLQ Errors",
            "viz_type": "pie",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps({"viz_type": "pie", "groupby": ["error_type"], "metric": "count"}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT error_type, COUNT(*) as count FROM bronze.dlq_errors GROUP BY error_type"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Hourly Trip Volume",
            "viz_type": "echarts_timeseries_line",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "echarts_timeseries_line",
                    "x_axis": "hour",
                    "metrics": ["count"],
                }
            ),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT DATE_TRUNC('hour', pickup_time) as hour, COUNT(*) as count FROM gold.fact_trips WHERE pickup_time >= NOW() - INTERVAL '24 hours' GROUP BY DATE_TRUNC('hour', pickup_time)"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Pipeline Lag",
            "viz_type": "big_number_total",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps({"metric": "lag_seconds", "viz_type": "big_number_total"}),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT TIMESTAMPDIFF(SECOND, MAX(pickup_time), NOW()) as lag_seconds FROM gold.fact_trips"
                        }
                    ],
                }
            ),
        },
        {
            "slice_name": "Trips by Zone Today",
            "viz_type": "deck_polygon",
            "datasource_id": database_id,
            "datasource_type": "table",
            "params": json.dumps(
                {
                    "viz_type": "deck_polygon",
                    "line_column": "zone_geometry",
                    "metric": "trip_count",
                }
            ),
            "query_context": json.dumps(
                {
                    "datasource": {"id": database_id, "type": "table"},
                    "queries": [
                        {
                            "custom_sql": "SELECT z.zone_geometry, COUNT(t.trip_id) as trip_count FROM gold.fact_trips t JOIN gold.dim_zones z ON t.pickup_zone_id = z.zone_id WHERE DATE(t.pickup_time) = CURRENT_DATE GROUP BY z.zone_geometry"
                        }
                    ],
                }
            ),
        },
    ]

    chart_ids = []
    for chart_config in charts:
        try:
            chart_id = client.create_chart(chart_config)
            chart_ids.append(chart_id)
            print(f"Created chart: {chart_config['slice_name']} (ID: {chart_id})")
        except Exception as e:
            print(f"Error creating chart {chart_config['slice_name']}: {e}")
            sys.exit(1)

    # Create dashboard
    dashboard_config = {
        "dashboard_title": "Operations Dashboard",
        "slug": "operations",
        "slices": chart_ids,
        "position_json": json.dumps(
            {
                "DASHBOARD_VERSION_KEY": "v2",
                "GRID_ID": {
                    "type": "GRID",
                    "id": "GRID_ID",
                    "children": [f"CHART-{i}" for i in range(len(chart_ids))],
                    "parents": ["ROOT_ID"],
                },
                **{
                    f"CHART-{i}": {
                        "type": "CHART",
                        "id": f"CHART-{i}",
                        "children": [],
                        "parents": ["GRID_ID"],
                        "meta": {
                            "width": 4 if i < 4 else (6 if i < 8 else 12),
                            "height": 4,
                            "chartId": chart_ids[i],
                        },
                    }
                    for i in range(len(chart_ids))
                },
            }
        ),
        "metadata": json.dumps(
            {
                "refresh_frequency": 300,
                "color_scheme": "supersetColors",
                "timed_refresh_immune_slices": [],
            }
        ),
    }

    try:
        dashboard_id = client.create_dashboard(dashboard_config)
        print(f"\nCreated dashboard: Operations Dashboard (ID: {dashboard_id})")
        print(f"Dashboard URL: http://localhost:8088/superset/dashboard/{dashboard_id}/")

        # Export dashboard as JSON
        dashboard_json = client.export_dashboard(dashboard_id)
        output_path = "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/analytics/superset/dashboards/operations-dashboard.json"
        with open(output_path, "wb") as f:
            f.write(dashboard_json)
        print(f"Dashboard exported to: {output_path}")

    except Exception as e:
        print(f"Error creating dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_operations_dashboard()
