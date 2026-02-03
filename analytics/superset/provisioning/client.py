"""Superset REST API client with proper error handling and retry logic."""

import json
import logging
import time
from typing import Any

import prison
import requests

from provisioning.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    ResourceNotFoundError,
    ServerBusyError,
    TransientError,
    ValidationError,
)
from provisioning.retry import retry_on_transient_error

logger = logging.getLogger(__name__)


class SupersetClient:
    """REST API client for Apache Superset.

    Features:
    - Automatic JWT token management with refresh before expiry
    - Proper RISON encoding for query parameters
    - HTTP status to exception type mapping
    - Connection pooling via requests.Session
    - Retry on transient errors
    """

    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "admin",
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Superset base URL (e.g., http://localhost:8088)
            username: Admin username
            password: Admin password
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._session = requests.Session()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._csrf_token: str | None = None
        self._token_expires_at: float = 0

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        # Refresh if token expires in less than 60 seconds
        if self._access_token and time.time() < self._token_expires_at - 60:
            return

        self.authenticate()

    @retry_on_transient_error(max_attempts=3)
    def authenticate(self) -> None:
        """Authenticate and obtain JWT tokens."""
        try:
            response = self._session.post(
                f"{self.base_url}/api/v1/security/login",
                json={
                    "username": self.username,
                    "password": self.password,
                    "provider": "db",
                },
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Superset: {e}") from e
        except requests.exceptions.Timeout as e:
            raise TransientError(f"Request timed out: {e}") from e

        if response.status_code == 401:
            raise AuthenticationError("Invalid username or password")

        self._handle_error_response(response)
        data = response.json()

        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        # Token typically valid for 1 hour, set expiry conservatively
        self._token_expires_at = time.time() + 3600

        # Get CSRF token for POST/PUT/DELETE requests
        self._fetch_csrf_token()

        logger.debug("Successfully authenticated with Superset")

    def _fetch_csrf_token(self) -> None:
        """Fetch CSRF token from Superset."""
        response = self._session.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            headers=self._auth_headers(),
            timeout=10,
        )
        if response.ok:
            self._csrf_token = response.json().get("result")
            logger.debug("CSRF token obtained")

    def _auth_headers(self) -> dict[str, str]:
        """Get headers with authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if self._csrf_token:
            headers["X-CSRFToken"] = self._csrf_token
        return headers

    def _handle_error_response(self, response: requests.Response) -> None:
        """Convert HTTP error responses to appropriate exceptions."""
        if response.ok:
            return

        status = response.status_code

        # Try to get error message from response
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
            errors = error_data.get("errors", [])
        except ValueError:
            message = response.text
            errors = []

        # Map status codes to exceptions
        if status == 401:
            raise AuthenticationError(message)
        elif status == 404:
            raise ResourceNotFoundError("Resource", message)
        elif status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(int(retry_after) if retry_after else None)
        elif status in (400, 422):
            raise ValidationError(message, errors)
        elif status == 503:
            raise ServerBusyError(f"Server unavailable: {message}")
        elif status >= 500:
            raise TransientError(f"Server error ({status}): {message}")
        else:
            raise TransientError(f"HTTP {status}: {message}")

    @retry_on_transient_error(max_attempts=5)
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., /api/v1/database)
            params: Query parameters
            json_data: JSON body for POST/PUT
            timeout: Request timeout in seconds

        Returns:
            Response JSON data
        """
        self._ensure_authenticated()

        url = f"{self.base_url}{endpoint}"

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=self._auth_headers(),
                timeout=timeout,
            )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Superset: {e}") from e
        except requests.exceptions.Timeout as e:
            raise TransientError(f"Request timed out: {e}") from e

        self._handle_error_response(response)

        # Handle empty responses (e.g., 204 No Content)
        if not response.content:
            return {}

        return response.json()

    def _rison_encode(self, data: dict[str, Any]) -> str:
        """Encode data as RISON for query parameters."""
        return prison.dumps(data)

    # =========================================================================
    # Health Check
    # =========================================================================

    def wait_for_healthy(self, timeout: int = 300, interval: int = 5) -> None:
        """Wait for Superset to be healthy.

        Args:
            timeout: Maximum wait time in seconds
            interval: Poll interval in seconds
        """
        start_time = time.time()
        last_error: Exception | None = None

        while time.time() - start_time < timeout:
            try:
                response = self._session.get(
                    f"{self.base_url}/health",
                    timeout=10,
                )
                if response.ok:
                    logger.info("Superset is healthy")
                    return
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.debug("Health check failed: %s", e)

            time.sleep(interval)

        raise ConnectionError(f"Superset not healthy after {timeout}s. Last error: {last_error}")

    # =========================================================================
    # Database Operations
    # =========================================================================

    def get_database_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a database connection by name.

        Args:
            name: Database name (e.g., "Rideshare Lakehouse")

        Returns:
            Database record or None if not found
        """
        # Use RISON to filter by database_name
        filters = self._rison_encode(
            {"filters": [{"col": "database_name", "opr": "eq", "value": name}]}
        )
        response = self._request("GET", "/api/v1/database/", params={"q": filters})

        databases = response.get("result", [])
        if databases:
            return databases[0]
        return None

    def get_database_id(self, name: str) -> int:
        """Get database ID by name, raising if not found.

        Args:
            name: Database name

        Returns:
            Database ID

        Raises:
            ResourceNotFoundError: If database doesn't exist
        """
        db = self.get_database_by_name(name)
        if db is None:
            raise ResourceNotFoundError("Database", name)
        return db["id"]

    # =========================================================================
    # Dataset Operations
    # =========================================================================

    def get_dataset_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a dataset by name.

        Args:
            name: Dataset name

        Returns:
            Dataset record or None if not found
        """
        filters = self._rison_encode(
            {"filters": [{"col": "table_name", "opr": "eq", "value": name}]}
        )
        response = self._request("GET", "/api/v1/dataset/", params={"q": filters})

        datasets = response.get("result", [])
        if datasets:
            return datasets[0]
        return None

    def get_or_create_dataset(
        self,
        database_id: int,
        name: str,
        sql: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Get existing dataset or create new one (idempotent).

        Args:
            database_id: Database connection ID
            name: Dataset name
            sql: SQL query for virtual dataset
            description: Optional description

        Returns:
            Dataset record
        """
        existing = self.get_dataset_by_name(name)
        if existing:
            logger.debug("Dataset '%s' already exists (id=%d)", name, existing["id"])
            return existing

        logger.info("Creating dataset: %s", name)
        try:
            response = self._request(
                "POST",
                "/api/v1/dataset/",
                json_data={
                    "database": database_id,
                    "table_name": name,
                    "sql": sql,
                },
            )
            return response
        except ValidationError as e:
            # Handle race condition: dataset may have been created by a timed-out request
            if "already exists" in str(e):
                logger.debug("Dataset '%s' was created by a previous request, fetching it", name)
                existing = self.get_dataset_by_name(name)
                if existing:
                    return existing
            raise

    def delete_dataset(self, dataset_id: int) -> None:
        """Delete a dataset by ID.

        Args:
            dataset_id: Dataset ID
        """
        self._request("DELETE", f"/api/v1/dataset/{dataset_id}")
        logger.info("Deleted dataset id=%d", dataset_id)

    # =========================================================================
    # Chart Operations
    # =========================================================================

    def get_chart_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a chart by name (slice_name).

        Args:
            name: Chart name

        Returns:
            Chart record or None if not found
        """
        filters = self._rison_encode(
            {"filters": [{"col": "slice_name", "opr": "eq", "value": name}]}
        )
        response = self._request("GET", "/api/v1/chart/", params={"q": filters})

        charts = response.get("result", [])
        if charts:
            return charts[0]
        return None

    def get_or_create_chart(
        self,
        name: str,
        datasource_id: int,
        viz_type: str,
        params: dict[str, Any],
        query_context: dict[str, Any] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Get existing chart or create new one (idempotent).

        Args:
            name: Chart name
            datasource_id: Dataset ID
            viz_type: Visualization type (e.g., "big_number_total", "bar", "pie")
            params: Chart-specific parameters
            query_context: Query context for chart data fetching
            description: Optional description

        Returns:
            Chart record
        """
        existing = self.get_chart_by_name(name)
        if existing:
            logger.debug("Chart '%s' already exists (id=%d)", name, existing["id"])
            return existing

        logger.info("Creating chart: %s (type=%s)", name, viz_type)

        json_data: dict[str, Any] = {
            "slice_name": name,
            "datasource_id": datasource_id,
            "datasource_type": "table",
            "viz_type": viz_type,
            "params": json.dumps(params),
            "description": description,
        }

        # Add query_context if provided
        if query_context is not None:
            json_data["query_context"] = json.dumps(query_context)

        response = self._request(
            "POST",
            "/api/v1/chart/",
            json_data=json_data,
        )
        return response

    def delete_chart(self, chart_id: int) -> None:
        """Delete a chart by ID.

        Args:
            chart_id: Chart ID
        """
        self._request("DELETE", f"/api/v1/chart/{chart_id}")
        logger.info("Deleted chart id=%d", chart_id)

    # =========================================================================
    # Dashboard Operations
    # =========================================================================

    def get_dashboard_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Find a dashboard by slug.

        Args:
            slug: Dashboard slug (URL-friendly identifier)

        Returns:
            Dashboard record or None if not found
        """
        filters = self._rison_encode({"filters": [{"col": "slug", "opr": "eq", "value": slug}]})
        response = self._request("GET", "/api/v1/dashboard/", params={"q": filters})

        dashboards = response.get("result", [])
        if dashboards:
            return dashboards[0]
        return None

    def get_or_create_dashboard(
        self,
        title: str,
        slug: str,
        published: bool = True,
    ) -> dict[str, Any]:
        """Get existing dashboard or create new one (idempotent).

        Args:
            title: Dashboard title
            slug: URL-friendly slug
            published: Whether dashboard is published

        Returns:
            Dashboard record
        """
        existing = self.get_dashboard_by_slug(slug)
        if existing:
            logger.debug("Dashboard '%s' already exists (id=%d)", slug, existing["id"])
            return existing

        logger.info("Creating dashboard: %s (slug=%s)", title, slug)
        response = self._request(
            "POST",
            "/api/v1/dashboard/",
            json_data={
                "dashboard_title": title,
                "slug": slug,
                "published": published,
            },
        )
        return response

    def update_dashboard(
        self,
        dashboard_id: int,
        position_json: dict[str, Any] | None = None,
        json_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update dashboard layout and metadata.

        Args:
            dashboard_id: Dashboard ID
            position_json: Chart positions layout
            json_metadata: Dashboard metadata (refresh interval, filters, etc.)

        Returns:
            Updated dashboard record
        """
        payload: dict[str, Any] = {}
        if position_json is not None:
            payload["position_json"] = json.dumps(position_json)
        if json_metadata is not None:
            payload["json_metadata"] = json.dumps(json_metadata)

        if not payload:
            # Nothing to update
            return self._request("GET", f"/api/v1/dashboard/{dashboard_id}")

        logger.debug("Updating dashboard id=%d", dashboard_id)
        return self._request("PUT", f"/api/v1/dashboard/{dashboard_id}", json_data=payload)

    def add_charts_to_dashboard(
        self,
        dashboard_id: int,
        chart_ids: list[int],
    ) -> dict[str, Any]:
        """Add charts to a dashboard.

        Args:
            dashboard_id: Dashboard ID
            chart_ids: List of chart IDs to add

        Returns:
            Updated dashboard
        """
        # Get current dashboard to merge charts
        dashboard = self._request("GET", f"/api/v1/dashboard/{dashboard_id}")

        # Get position_json if exists
        position_json_str = dashboard.get("result", {}).get("position_json", "{}")
        try:
            position_json = json.loads(position_json_str) if position_json_str else {}
        except (json.JSONDecodeError, TypeError):
            position_json = {}

        # Build layout with chart positions
        for chart_id in chart_ids:
            chart_key = f"CHART-{chart_id}"
            position_json[chart_key] = {
                "type": "CHART",
                "id": chart_key,
                "children": [],
                "meta": {
                    "chartId": chart_id,
                    "width": 6,
                    "height": 4,
                },
            }

        # Update position_json
        return self.update_dashboard(dashboard_id, position_json=position_json)

    def delete_dashboard(self, dashboard_id: int) -> None:
        """Delete a dashboard by ID.

        Args:
            dashboard_id: Dashboard ID
        """
        self._request("DELETE", f"/api/v1/dashboard/{dashboard_id}")
        logger.info("Deleted dashboard id=%d", dashboard_id)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def close(self) -> None:
        """Close the session and clean up resources."""
        self._session.close()

    def __enter__(self) -> "SupersetClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()
