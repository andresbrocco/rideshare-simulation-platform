"""HTTP client for querying Prometheus instant API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Synchronous HTTP client for Prometheus instant queries."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=5.0)

    def query_instant(self, promql: str) -> float | None:
        """Execute an instant query and return the scalar value, or None."""
        try:
            resp = self._client.get(
                "/api/v1/query",
                params={"query": promql},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                return None
            results = data.get("data", {}).get("result", [])
            if not results:
                return None
            # Take the first result's value (instant query returns [timestamp, value])
            value_str = results[0].get("value", [None, None])[1]
            if value_str is None:
                return None
            value = float(value_str)
            # NaN / Inf from Prometheus → treat as missing
            if value != value or value == float("inf") or value == float("-inf"):
                return None
            return value
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.debug("Prometheus query failed for %r: %s", promql, exc)
            return None

    def get_infrastructure_headroom(self) -> float | None:
        """Fetch the composite infrastructure headroom from Prometheus recording rules."""
        return self.query_instant("rideshare:infrastructure:headroom")

    def is_available(self) -> bool:
        """Test connectivity to Prometheus."""
        try:
            resp = self._client.get("/api/v1/status/buildinfo")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
