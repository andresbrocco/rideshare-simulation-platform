"""HTTP client for querying Prometheus instant API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# PromQL queries for each saturation signal
QUERIES: dict[str, str] = {
    "kafka_lag": "sum(kafka_consumergroup_lag)",
    "simpy_queue": "simulation_simpy_events",
    "cpu_percent": "simulation_cpu_percent",
    "memory_percent": "simulation_memory_percent",
    "produced_rate": "sum(rate(simulation_events_total[30s]))",
    "consumed_rate": "sum(rate(stream_processor_messages_consumed_total[30s]))",
    "real_time_ratio": "simulation_real_time_ratio",
    "speed_multiplier": "simulation_speed_multiplier",
}


@dataclass(frozen=True)
class SaturationMetrics:
    """Snapshot of all performance-relevant metrics from Prometheus."""

    kafka_lag: float | None
    simpy_queue: float | None
    cpu_percent: float | None
    memory_percent: float | None
    produced_rate: float | None
    consumed_rate: float | None
    real_time_ratio: float | None
    speed_multiplier: float | None


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

    def get_saturation_metrics(self) -> SaturationMetrics | None:
        """Fetch all saturation metrics in one pass.

        Returns None if Prometheus is unreachable.
        Individual fields may be None when the metric hasn't been scraped yet.
        """
        try:
            values: dict[str, float | None] = {}
            for key, promql in QUERIES.items():
                values[key] = self.query_instant(promql)
            return SaturationMetrics(**values)
        except Exception as exc:
            logger.warning("Failed to fetch saturation metrics: %s", exc)
            return None

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
