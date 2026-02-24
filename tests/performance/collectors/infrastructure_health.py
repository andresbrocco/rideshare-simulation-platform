"""Infrastructure health collector via Simulation API /metrics/infrastructure endpoint."""

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import TestConfig


@dataclass
class ServiceHealthSample:
    """A single health check sample for a service."""

    name: str
    latency_ms: float | None
    status: str
    message: str | None
    threshold_degraded: float | None
    threshold_unhealthy: float | None


class InfrastructureHealthCollector:
    """Collects service health latencies from the /metrics/infrastructure API endpoint.

    Follows the same pattern as DockerStatsCollector: constructor takes TestConfig,
    collect() returns None on error, and is_available() checks connectivity.
    """

    def __init__(self, config: TestConfig) -> None:
        self._base_url = config.api.base_url
        self._api_key = config.api.api_key
        self._timeout = min(config.api.timeout, 10.0)

    def collect(self) -> dict[str, ServiceHealthSample] | None:
        """Collect health latencies for all services.

        Returns:
            Dict mapping service display name to ServiceHealthSample,
            or None if the endpoint is unreachable or returns an error.
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    f"{self._base_url}/metrics/infrastructure",
                    headers={"X-API-Key": self._api_key},
                )
                if response.status_code != 200:
                    return None

                data: dict[str, Any] = response.json()
                services: list[dict[str, Any]] = data.get("services", [])

                result: dict[str, ServiceHealthSample] = {}
                for svc in services:
                    name = svc.get("name", "")
                    if not name:
                        continue
                    result[name] = ServiceHealthSample(
                        name=name,
                        latency_ms=svc.get("latency_ms"),
                        status=svc.get("status", "unknown"),
                        message=svc.get("message"),
                        threshold_degraded=svc.get("threshold_degraded"),
                        threshold_unhealthy=svc.get("threshold_unhealthy"),
                    )
                return result

        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def is_available(self) -> bool:
        """Check if the infrastructure health endpoint is reachable."""
        return self.collect() is not None
