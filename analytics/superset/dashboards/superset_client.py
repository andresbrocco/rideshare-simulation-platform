#!/usr/bin/env python3
"""
Shared Superset API client for programmatic dashboard provisioning.

This module provides a reusable SupersetClient class with:
- Environment variable support for credentials
- Configurable timeouts
- Idempotency methods (dashboard_exists, dataset_exists, chart_exists)
- get_or_create_* methods for safe provisioning
- Health check with retry logic

Usage:
    from superset_client import SupersetClient

    client = SupersetClient(base_url="http://localhost:8088")
    if client.authenticate():
        dashboard_id = client.get_or_create_dashboard("My Dashboard", "my-dashboard")
"""

import json
import os
import time
from typing import Optional

import requests


# Database name must match what docker-entrypoint.sh creates
DATABASE_NAME = "Rideshare Lakehouse"


class SupersetClient:
    """Client for Superset REST API with idempotent operations."""

    def __init__(
        self,
        base_url: str = "http://localhost:8088",
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 10,
        retry_delay: int = 3,
    ):
        """Initialize Superset client.

        Args:
            base_url: Superset base URL
            username: Admin username (defaults to SUPERSET_ADMIN_USERNAME env var or "admin")
            password: Admin password (defaults to SUPERSET_ADMIN_PASSWORD env var or "admin")
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for health check and auth
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.username = username or os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")
        self.password = password or os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self._authenticated = False
        self._database_id: Optional[int] = None

    def wait_for_superset(self) -> bool:
        """Wait for Superset to be ready.

        Returns:
            True if Superset is healthy, False otherwise
        """
        for i in range(self.max_retries):
            try:
                response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
                if response.status_code == 200:
                    print("Superset is ready")
                    return True
            except requests.exceptions.RequestException:
                pass
            print(f"Waiting for Superset... ({i + 1}/{self.max_retries})")
            time.sleep(self.retry_delay)
        print("Superset not available after all retries")
        return False

    def authenticate(self) -> bool:
        """Authenticate with Superset API.

        Returns:
            True if authentication successful, False otherwise
        """
        if not self.wait_for_superset():
            return False

        login_url = f"{self.base_url}/api/v1/security/login"
        login_data = {
            "username": self.username,
            "password": self.password,
            "provider": "db",
            "refresh": True,
        }

        for i in range(self.max_retries):
            try:
                response = self.session.post(login_url, json=login_data, timeout=self.timeout)
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    self.session.headers.update({"Authorization": f"Bearer {access_token}"})
                    self._get_csrf_token()
                    self._authenticated = True
                    print("Authentication successful")
                    return True
                print(f"Login attempt {i + 1} failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Login attempt {i + 1} error: {e}")
            time.sleep(self.retry_delay)

        print("Authentication failed after all retries")
        return False

    def _get_csrf_token(self) -> None:
        """Get CSRF token for API requests."""
        csrf_url = f"{self.base_url}/api/v1/security/csrf_token/"
        response = self.session.get(csrf_url, timeout=self.timeout)
        if response.status_code == 200:
            csrf_token = response.json().get("result")
            self.session.headers.update(
                {
                    "X-CSRFToken": csrf_token,
                    "Referer": self.base_url,
                    "Content-Type": "application/json",
                }
            )

    def get_database_id(self, database_name: str = DATABASE_NAME) -> Optional[int]:
        """Get database ID by name.

        Args:
            database_name: Name of the database

        Returns:
            Database ID if found, None otherwise
        """
        if self._database_id is not None:
            return self._database_id

        url = f"{self.base_url}/api/v1/database/"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                databases = response.json().get("result", [])
                for db in databases:
                    if db.get("database_name") == database_name:
                        self._database_id = db.get("id")
                        return self._database_id
        except requests.exceptions.RequestException as e:
            print(f"Error fetching databases: {e}")
        return None

    # --- Existence checks ---

    def dashboard_exists(self, slug: str) -> bool:
        """Check if a dashboard with the given slug exists.

        Args:
            slug: Dashboard slug to check

        Returns:
            True if dashboard exists, False otherwise
        """
        if not self._authenticated:
            return False

        url = f"{self.base_url}/api/v1/dashboard/"
        params = {"q": f"(filters:!((col:slug,opr:eq,value:{slug})))"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                return result.get("count", 0) > 0
        except requests.exceptions.RequestException as e:
            print(f"Error checking dashboard {slug}: {e}")
        return False

    def dataset_exists(self, table_name: str) -> Optional[int]:
        """Check if a dataset with the given table name exists.

        Args:
            table_name: Virtual dataset table name

        Returns:
            Dataset ID if exists, None otherwise
        """
        if not self._authenticated:
            return None

        url = f"{self.base_url}/api/v1/dataset/"
        params = {"q": f"(filters:!((col:table_name,opr:eq,value:{table_name})))"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                datasets = result.get("result", [])
                if datasets:
                    return datasets[0].get("id")
        except requests.exceptions.RequestException as e:
            print(f"Error checking dataset {table_name}: {e}")
        return None

    def chart_exists(self, slice_name: str) -> Optional[int]:
        """Check if a chart with the given name exists.

        Args:
            slice_name: Chart name

        Returns:
            Chart ID if exists, None otherwise
        """
        if not self._authenticated:
            return None

        url = f"{self.base_url}/api/v1/chart/"
        params = {"q": f"(filters:!((col:slice_name,opr:eq,value:'{slice_name}')))"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                charts = result.get("result", [])
                if charts:
                    return charts[0].get("id")
        except requests.exceptions.RequestException as e:
            print(f"Error checking chart {slice_name}: {e}")
        return None

    def get_dashboard_id(self, slug: str) -> Optional[int]:
        """Get dashboard ID by slug.

        Args:
            slug: Dashboard slug

        Returns:
            Dashboard ID if found, None otherwise
        """
        if not self._authenticated:
            return None

        url = f"{self.base_url}/api/v1/dashboard/"
        params = {"q": f"(filters:!((col:slug,opr:eq,value:{slug})))"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                dashboards = result.get("result", [])
                if dashboards:
                    return dashboards[0].get("id")
        except requests.exceptions.RequestException as e:
            print(f"Error getting dashboard {slug}: {e}")
        return None

    # --- Create operations ---

    def create_dataset(self, database_id: int, table_name: str, sql: str) -> int:
        """Create a virtual dataset from SQL query.

        Args:
            database_id: Database ID
            table_name: Virtual dataset name
            sql: SQL query for the virtual dataset

        Returns:
            Dataset ID

        Raises:
            Exception: If creation fails
        """
        dataset_config = {
            "database": database_id,
            "schema": "",
            "table_name": table_name,
            "sql": sql,
            "owners": [],
        }

        url = f"{self.base_url}/api/v1/dataset/"
        response = self.session.post(url, json=dataset_config, timeout=self.timeout)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create dataset {table_name}: {response.text}")

    def create_chart(
        self, dataset_id: int, slice_name: str, viz_type: str, params: Optional[dict] = None
    ) -> int:
        """Create a chart.

        Args:
            dataset_id: Dataset ID
            slice_name: Chart name
            viz_type: Visualization type
            params: Optional chart parameters

        Returns:
            Chart ID

        Raises:
            Exception: If creation fails
        """
        chart_params = params or {"viz_type": viz_type, "metrics": ["count"], "adhoc_filters": []}
        chart_config = {
            "slice_name": slice_name,
            "viz_type": viz_type,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps(chart_params),
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
        response = self.session.post(url, json=chart_config, timeout=self.timeout)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create chart {slice_name}: {response.text}")

    def create_dashboard(self, title: str, slug: str, refresh_frequency: int = 300) -> int:
        """Create an empty dashboard.

        Args:
            title: Dashboard title
            slug: Dashboard URL slug
            refresh_frequency: Auto-refresh interval in seconds

        Returns:
            Dashboard ID

        Raises:
            Exception: If creation fails
        """
        dashboard_config = {"dashboard_title": title, "slug": slug, "published": True}

        url = f"{self.base_url}/api/v1/dashboard/"
        response = self.session.post(url, json=dashboard_config, timeout=self.timeout)

        if response.status_code in [200, 201]:
            return response.json().get("id")

        raise Exception(f"Failed to create dashboard {slug}: {response.text}")

    def update_dashboard(
        self,
        dashboard_id: int,
        chart_ids: list[int],
        layout: Optional[list[tuple[int, int]]] = None,
        refresh_frequency: int = 300,
    ) -> None:
        """Update dashboard with charts and metadata.

        Args:
            dashboard_id: Dashboard ID
            chart_ids: List of chart IDs to add
            layout: Optional list of (width, height) tuples for each chart
            refresh_frequency: Auto-refresh interval in seconds

        Raises:
            Exception: If update fails
        """
        position_json: dict = {
            "DASHBOARD_VERSION_KEY": "v2",
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [],
                "parents": ["ROOT_ID"],
            },
        }

        for i, chart_id in enumerate(chart_ids):
            chart_key = f"CHART-{i}"
            grid_children = position_json["GRID_ID"]["children"]
            if isinstance(grid_children, list):
                grid_children.append(chart_key)
            width, height = layout[i] if layout and i < len(layout) else (4, 4)
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
        response = self.session.put(url, json=update_config, timeout=self.timeout)

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to update dashboard: {response.text}")

    def associate_charts_with_dashboard(self, dashboard_id: int, chart_ids: list[int]) -> None:
        """Associate charts with dashboard.

        Args:
            dashboard_id: Dashboard ID
            chart_ids: List of chart IDs to associate

        Raises:
            Exception: If association fails
        """
        for chart_id in chart_ids:
            chart_url = f"{self.base_url}/api/v1/chart/{chart_id}"
            update_data = {"dashboards": [dashboard_id]}

            response = self.session.put(chart_url, json=update_data, timeout=self.timeout)
            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to associate chart {chart_id}: {response.text}")

    def delete_dashboard(self, dashboard_id: int) -> bool:
        """Delete a dashboard.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            True if deleted successfully, False otherwise
        """
        url = f"{self.base_url}/api/v1/dashboard/{dashboard_id}"
        try:
            response = self.session.delete(url, timeout=self.timeout)
            return response.status_code in [200, 204]
        except requests.exceptions.RequestException as e:
            print(f"Error deleting dashboard {dashboard_id}: {e}")
            return False

    # --- Get or create operations (idempotent) ---

    def get_or_create_dataset(self, database_id: int, table_name: str, sql: str) -> int:
        """Get existing dataset or create new one.

        Args:
            database_id: Database ID
            table_name: Virtual dataset name
            sql: SQL query for the virtual dataset

        Returns:
            Dataset ID
        """
        existing_id = self.dataset_exists(table_name)
        if existing_id:
            print(f"  SKIP: Dataset '{table_name}' already exists (ID: {existing_id})")
            return existing_id

        dataset_id = self.create_dataset(database_id, table_name, sql)
        print(f"  CREATE: Dataset '{table_name}' (ID: {dataset_id})")
        return dataset_id

    def get_or_create_chart(
        self, dataset_id: int, slice_name: str, viz_type: str, params: Optional[dict] = None
    ) -> int:
        """Get existing chart or create new one.

        Args:
            dataset_id: Dataset ID
            slice_name: Chart name
            viz_type: Visualization type
            params: Optional chart parameters

        Returns:
            Chart ID
        """
        existing_id = self.chart_exists(slice_name)
        if existing_id:
            print(f"  SKIP: Chart '{slice_name}' already exists (ID: {existing_id})")
            return existing_id

        chart_id = self.create_chart(dataset_id, slice_name, viz_type, params)
        print(f"  CREATE: Chart '{slice_name}' (ID: {chart_id})")
        return chart_id

    def get_or_create_dashboard(self, title: str, slug: str, refresh_frequency: int = 300) -> int:
        """Get existing dashboard or create new one.

        Args:
            title: Dashboard title
            slug: Dashboard URL slug
            refresh_frequency: Auto-refresh interval in seconds

        Returns:
            Dashboard ID
        """
        existing_id = self.get_dashboard_id(slug)
        if existing_id:
            print(f"  SKIP: Dashboard '{slug}' already exists (ID: {existing_id})")
            return existing_id

        dashboard_id = self.create_dashboard(title, slug, refresh_frequency)
        print(f"  CREATE: Dashboard '{slug}' (ID: {dashboard_id})")
        return dashboard_id
