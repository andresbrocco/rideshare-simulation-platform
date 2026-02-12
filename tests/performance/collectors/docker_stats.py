"""Docker container stats collection via cAdvisor API."""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from ..config import CONTAINER_CONFIG, TestConfig


@dataclass
class MetricSample:
    """A single metric sample for a container."""

    container_name: str
    timestamp: float
    timestamp_iso: str
    memory_used_mb: float
    memory_limit_mb: float
    memory_percent: float
    cpu_percent: float


class DockerStatsCollector:
    """Collects container metrics from cAdvisor API.

    Implements patterns from services/simulation/src/api/routes/metrics.py.
    """

    def __init__(self, config: TestConfig) -> None:
        self.config = config
        self.cadvisor_url = f"{config.docker.cadvisor_url}/api/v1.3/docker/"

    def _fetch_cadvisor_stats(self) -> dict[str, Any] | None:
        """Fetch container stats from cAdvisor API.

        Returns:
            Dict mapping container name to stats, or None if unavailable.
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(self.cadvisor_url)
                if response.status_code == 200:
                    result: dict[str, Any] = response.json()
                    return result
        except Exception:
            pass
        return None

    def _find_container_in_cadvisor(
        self, container_name: str, cadvisor_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Find a container's data in cAdvisor response by name."""
        for key, data in cadvisor_data.items():
            container_data: dict[str, Any] = data
            # Check if the container name is in the key or in the aliases
            if container_name in key:
                return container_data
            aliases: list[str] = container_data.get("aliases", [])
            if container_name in aliases:
                return container_data
            # Check the name field
            name: str = container_data.get("name", "")
            if name.endswith(container_name):
                return container_data
        return None

    def _calculate_cpu_percent(self, stats: list[dict[str, Any]]) -> float:
        """Calculate CPU percentage from cAdvisor stats.

        Uses the difference between the last two stats samples.
        Returns 0.0 if insufficient data.
        """
        if len(stats) < 2:
            return 0.0

        curr = stats[-1]
        prev = stats[-2]

        curr_cpu = curr.get("cpu", {}).get("usage", {}).get("total", 0)
        prev_cpu = prev.get("cpu", {}).get("usage", {}).get("total", 0)

        curr_time = curr.get("timestamp", "")
        prev_time = prev.get("timestamp", "")

        try:
            curr_dt = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))
            prev_dt = datetime.fromisoformat(prev_time.replace("Z", "+00:00"))
            time_delta_ns = (curr_dt - prev_dt).total_seconds() * 1e9
        except Exception:
            return 0.0

        if time_delta_ns <= 0:
            return 0.0

        cpu_delta = curr_cpu - prev_cpu
        # cAdvisor reports CPU in nanoseconds, normalize to percentage
        cpu_percent = (cpu_delta / time_delta_ns) * 100

        return float(max(0.0, cpu_percent))

    def _parse_container_resource_metrics(
        self, container_name: str, data: dict[str, Any]
    ) -> tuple[float, float, float, float]:
        """Parse container resource metrics from cAdvisor data.

        Memory limit is extracted from cAdvisor's spec.memory.limit field,
        which reflects the actual Docker mem_limit setting from compose.yml.

        Returns:
            (memory_used_mb, memory_limit_mb, memory_percent, cpu_percent)
        """
        stats = data.get("stats", [])
        latest = stats[-1] if stats else {}

        # Memory metrics (working_set is the relevant metric for actual usage)
        memory = latest.get("memory", {})
        memory_working_set = memory.get("working_set", 0)
        memory_used_mb = memory_working_set / (1024 * 1024)

        # Get memory limit from cAdvisor spec (actual Docker container limit)
        spec = data.get("spec", {})
        memory_limit_bytes = spec.get("memory", {}).get("limit", 0)

        # Handle "unlimited" case: when no mem_limit is set in Docker,
        # cAdvisor reports max uint64 or a very large value
        MAX_REASONABLE_LIMIT = 64 * 1024 * 1024 * 1024  # 64 GB
        if memory_limit_bytes == 0 or memory_limit_bytes > MAX_REASONABLE_LIMIT:
            memory_limit_mb = 0.0
        else:
            memory_limit_mb = memory_limit_bytes / (1024 * 1024)

        # Calculate memory percentage
        memory_percent = (memory_used_mb / memory_limit_mb * 100) if memory_limit_mb > 0 else 0.0

        # CPU percentage
        cpu_percent = self._calculate_cpu_percent(stats)

        return (
            round(memory_used_mb, 1),
            round(memory_limit_mb, 1),
            round(memory_percent, 1),
            round(cpu_percent, 1),
        )

    def get_container_stats(self, container_name: str) -> MetricSample | None:
        """Get metrics for a specific container.

        Args:
            container_name: Name of the container to get stats for.

        Returns:
            MetricSample with current metrics, or None if unavailable.
        """
        cadvisor_data = self._fetch_cadvisor_stats()
        if not cadvisor_data:
            return None

        container_data = self._find_container_in_cadvisor(container_name, cadvisor_data)
        if not container_data:
            return None

        memory_used_mb, memory_limit_mb, memory_percent, cpu_percent = (
            self._parse_container_resource_metrics(container_name, container_data)
        )

        now = time.time()
        return MetricSample(
            container_name=container_name,
            timestamp=now,
            timestamp_iso=datetime.fromtimestamp(now).isoformat(),
            memory_used_mb=memory_used_mb,
            memory_limit_mb=memory_limit_mb,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
        )

    def get_all_container_stats(self) -> dict[str, MetricSample]:
        """Get metrics for all known containers.

        Returns:
            Dict mapping container name to MetricSample.
            Containers not found in cAdvisor are omitted.
        """
        cadvisor_data = self._fetch_cadvisor_stats()
        if not cadvisor_data:
            return {}

        results: dict[str, MetricSample] = {}
        now = time.time()
        timestamp_iso = datetime.fromtimestamp(now).isoformat()

        for container_name in CONTAINER_CONFIG:
            container_data = self._find_container_in_cadvisor(container_name, cadvisor_data)
            if not container_data:
                continue

            memory_used_mb, memory_limit_mb, memory_percent, cpu_percent = (
                self._parse_container_resource_metrics(container_name, container_data)
            )

            results[container_name] = MetricSample(
                container_name=container_name,
                timestamp=now,
                timestamp_iso=timestamp_iso,
                memory_used_mb=memory_used_mb,
                memory_limit_mb=memory_limit_mb,
                memory_percent=memory_percent,
                cpu_percent=cpu_percent,
            )

        return results

    def is_available(self) -> bool:
        """Check if cAdvisor is available."""
        return self._fetch_cadvisor_stats() is not None
