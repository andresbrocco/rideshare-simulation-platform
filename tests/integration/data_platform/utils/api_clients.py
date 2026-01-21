"""HTTP client utilities for external service APIs."""

import time
from typing import Dict, Any, Optional, List
import httpx


class AirflowClient:
    """HTTP client for Airflow REST API with basic auth."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialize Airflow client.

        Args:
            base_url: Airflow webserver URL (e.g., http://localhost:8082)
            username: Airflow admin username
            password: Airflow admin password
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(auth=(username, password), timeout=30.0)

    def trigger_dag(self, dag_id: str, conf: Optional[Dict[str, Any]] = None) -> str:
        """Trigger DAG run.

        Args:
            dag_id: DAG identifier
            conf: Optional DAG run configuration

        Returns:
            DAG run ID

        Raises:
            httpx.HTTPError: On API error
        """
        payload = {"conf": conf or {}}
        response = self.client.post(
            f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns", json=payload
        )
        response.raise_for_status()
        return response.json()["dag_run_id"]

    def get_dag_run_state(self, dag_id: str, dag_run_id: str) -> str:
        """Get DAG run state.

        Args:
            dag_id: DAG identifier
            dag_run_id: DAG run ID

        Returns:
            State string (e.g., 'success', 'running', 'failed')
        """
        response = self.client.get(
            f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
        )
        response.raise_for_status()
        return response.json()["state"]

    def list_dags(self) -> List[Dict[str, Any]]:
        """List all DAGs.

        Returns:
            List of DAG metadata dictionaries
        """
        response = self.client.get(f"{self.base_url}/api/v1/dags")
        response.raise_for_status()
        return response.json()["dags"]

    def wait_for_dag_completion(
        self,
        dag_id: str,
        dag_run_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 5.0,
    ) -> str:
        """Wait for DAG run to complete.

        Args:
            dag_id: DAG identifier
            dag_run_id: DAG run ID
            timeout_seconds: Maximum wait time
            poll_interval: Polling interval in seconds

        Returns:
            Final state ('success' or 'failed')

        Raises:
            TimeoutError: If DAG doesn't complete within timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            state = self.get_dag_run_state(dag_id, dag_run_id)
            if state in ("success", "failed"):
                return state
            time.sleep(poll_interval)

        raise TimeoutError(
            f"DAG {dag_id} run {dag_run_id} did not complete within {timeout_seconds}s"
        )

    def close(self):
        """Close HTTP client."""
        self.client.close()


class SupersetClient:
    """HTTP client for Superset REST API with session-based auth."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialize Superset client.

        Args:
            base_url: Superset URL (e.g., http://localhost:8088)
            username: Superset admin username
            password: Superset admin password
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        self._login(username, password)

    def _login(self, username: str, password: str) -> None:
        """Authenticate and store session token.

        Args:
            username: Username
            password: Password

        Raises:
            httpx.HTTPError: On login failure
        """
        response = self.client.post(
            f"{self.base_url}/api/v1/security/login",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        access_token = response.json()["access_token"]

        # Set Authorization header for subsequent requests
        self.client.headers.update({"Authorization": f"Bearer {access_token}"})

    def list_databases(self) -> List[Dict[str, Any]]:
        """List database connections.

        Returns:
            List of database metadata dictionaries
        """
        response = self.client.get(f"{self.base_url}/api/v1/database/")
        response.raise_for_status()
        return response.json()["result"]

    def execute_query(self, database_id: int, sql: str) -> Dict[str, Any]:
        """Execute SQL query via Superset API.

        Args:
            database_id: Database connection ID
            sql: SQL query string

        Returns:
            Query result dictionary
        """
        response = self.client.post(
            f"{self.base_url}/api/v1/sqllab/execute/",
            json={"database_id": database_id, "sql": sql},
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close HTTP client."""
        self.client.close()


class PrometheusClient:
    """HTTP client for Prometheus API (no auth required)."""

    def __init__(self, base_url: str):
        """Initialize Prometheus client.

        Args:
            base_url: Prometheus URL (e.g., http://localhost:9090)
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)

    def query_instant(self, query: str) -> Dict[str, Any]:
        """Execute instant query.

        Args:
            query: PromQL query string

        Returns:
            Query result dictionary with 'data' key
        """
        response = self.client.get(
            f"{self.base_url}/api/v1/query", params={"query": query}
        )
        response.raise_for_status()
        return response.json()

    def query_range(
        self, query: str, start: str, end: str, step: str = "1m"
    ) -> Dict[str, Any]:
        """Execute range query.

        Args:
            query: PromQL query string
            start: Start time (RFC3339 or Unix timestamp)
            end: End time (RFC3339 or Unix timestamp)
            step: Query resolution step (e.g., '1m')

        Returns:
            Query result dictionary
        """
        response = self.client.get(
            f"{self.base_url}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
        )
        response.raise_for_status()
        return response.json()

    def get_targets(self) -> List[Dict[str, Any]]:
        """Get scrape targets.

        Returns:
            List of target metadata dictionaries
        """
        response = self.client.get(f"{self.base_url}/api/v1/targets")
        response.raise_for_status()
        return response.json()["data"]["activeTargets"]

    def close(self):
        """Close HTTP client."""
        self.client.close()


class GrafanaClient:
    """HTTP client for Grafana API with API key auth."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialize Grafana client.

        Note: Uses basic auth instead of API key for simplicity.

        Args:
            base_url: Grafana URL (e.g., http://localhost:3001)
            username: Grafana admin username
            password: Grafana admin password
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(auth=(username, password), timeout=30.0)

    def get_dashboard(self, uid: str) -> Dict[str, Any]:
        """Get dashboard by UID.

        Args:
            uid: Dashboard UID

        Returns:
            Dashboard JSON
        """
        response = self.client.get(f"{self.base_url}/api/dashboards/uid/{uid}")
        response.raise_for_status()
        return response.json()

    def list_dashboards(self) -> List[Dict[str, Any]]:
        """List all dashboards.

        Returns:
            List of dashboard metadata dictionaries
        """
        response = self.client.get(f"{self.base_url}/api/search?type=dash-db")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """Check Grafana health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self.client.get(f"{self.base_url}/api/health")
            return response.status_code == 200
        except Exception:
            return False

    def close(self):
        """Close HTTP client."""
        self.client.close()


def retry_on_transient_error(
    callback, max_attempts: int = 3, backoff_seconds: float = 1.0
):
    """Retry callback on transient HTTP errors.

    Args:
        callback: Function to execute
        max_attempts: Maximum retry attempts
        backoff_seconds: Initial backoff time (doubles each retry)

    Returns:
        Callback result

    Raises:
        Exception: Last exception if all retries fail
    """
    last_exception = None
    for attempt in range(max_attempts):
        try:
            return callback()
        except httpx.HTTPStatusError as e:
            # Retry on 5xx server errors
            if e.response.status_code >= 500:
                last_exception = e
                if attempt < max_attempts - 1:
                    time.sleep(backoff_seconds * (2**attempt))
                    continue
            raise
        except httpx.RequestError as e:
            # Retry on network errors
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            raise

    raise last_exception
