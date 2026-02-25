"""Container metrics and simulation state collection via Prometheus API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from ..config import CONTAINER_CONFIG, TestConfig
from .docker_stats import MetricSample
from .infrastructure_health import ServiceHealthSample

MAX_REASONABLE_LIMIT = 64 * 1024 * 1024 * 1024  # 64 GB


@dataclass
class SimulationPrometheusMetrics:
    """Simulation-level metrics scraped from Prometheus."""

    active_trips: float
    throughput_events_per_sec: float  # sum(rate(simulation_events_total[30s]))
    speed_multiplier: int
    real_time_ratio: float | None


class PrometheusCollector:
    """Collects container resource metrics and simulation state from Prometheus.

    Replaces DockerStatsCollector and InfrastructureHealthCollector as a single
    facade. Uses a persistent httpx.Client for connection pooling across calls.
    Health latencies are not in Prometheus — those are delegated to the
    simulation API's /metrics/infrastructure endpoint.
    """

    def __init__(self, config: TestConfig) -> None:
        self._prometheus_url = config.docker.prometheus_url
        self._base_url = config.api.base_url
        self._api_key = config.api.api_key
        self._client = httpx.Client(timeout=5.0)

    def _query_prometheus(self, promql: str) -> list[dict[str, object]]:
        """Run an instant query against Prometheus and return the result array.

        Returns an empty list if the query fails or returns no results.
        """
        try:
            response = self._client.get(
                f"{self._prometheus_url}/api/v1/query",
                params={"query": promql},
            )
            if response.status_code != 200:
                return []
            payload: dict[str, object] = response.json()
            if payload.get("status") != "success":
                return []
            data = payload.get("data", {})
            if not isinstance(data, dict):
                return []
            result = data.get("result", [])
            if not isinstance(result, list):
                return []
            return result
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    def get_all_container_stats(self) -> dict[str, MetricSample]:
        """Get resource metrics for all known containers from Prometheus.

        Returns:
            Dict mapping container name to MetricSample.
            Containers not found in Prometheus are omitted.
        """
        cpu_results = self._query_prometheus(
            'sum by (name) (rate(container_cpu_usage_seconds_total{name=~"rideshare.*"}[30s])) * 100'
        )
        mem_used_results = self._query_prometheus(
            'container_memory_working_set_bytes{name=~"rideshare.*"}'
        )
        mem_limit_results = self._query_prometheus(
            'container_spec_memory_limit_bytes{name=~"rideshare.*"}'
        )

        # Index each result set by container name label for O(1) lookup
        cpu_by_name: dict[str, float] = {}
        for item in cpu_results:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric", {})
            if not isinstance(metric, dict):
                continue
            name = metric.get("name", "")
            value_pair = item.get("value", [])
            if isinstance(value_pair, list) and len(value_pair) >= 2:
                try:
                    cpu_by_name[str(name)] = float(str(value_pair[1]))
                except ValueError:
                    pass

        mem_used_by_name: dict[str, float] = {}
        for item in mem_used_results:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric", {})
            if not isinstance(metric, dict):
                continue
            name = metric.get("name", "")
            value_pair = item.get("value", [])
            if isinstance(value_pair, list) and len(value_pair) >= 2:
                try:
                    mem_used_by_name[str(name)] = float(str(value_pair[1]))
                except ValueError:
                    pass

        mem_limit_by_name: dict[str, float] = {}
        for item in mem_limit_results:
            if not isinstance(item, dict):
                continue
            metric = item.get("metric", {})
            if not isinstance(metric, dict):
                continue
            name = metric.get("name", "")
            value_pair = item.get("value", [])
            if isinstance(value_pair, list) and len(value_pair) >= 2:
                try:
                    raw_limit = float(str(value_pair[1]))
                    # Skip unlimited/unreported limits (same threshold as docker_stats.py)
                    if raw_limit > 0 and raw_limit <= MAX_REASONABLE_LIMIT:
                        mem_limit_by_name[str(name)] = raw_limit
                except ValueError:
                    pass

        now = time.time()
        timestamp_iso = datetime.fromtimestamp(now).isoformat()
        results: dict[str, MetricSample] = {}

        for container_name in CONTAINER_CONFIG:
            cpu_percent = round(cpu_by_name.get(container_name, 0.0), 1)
            mem_used_bytes = mem_used_by_name.get(container_name)
            if mem_used_bytes is None:
                continue

            mem_used_mb = round(mem_used_bytes / (1024 * 1024), 1)
            mem_limit_bytes = mem_limit_by_name.get(container_name, 0.0)
            mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 1) if mem_limit_bytes > 0 else 0.0
            mem_percent = round((mem_used_mb / mem_limit_mb * 100) if mem_limit_mb > 0 else 0.0, 1)

            results[container_name] = MetricSample(
                container_name=container_name,
                timestamp=now,
                timestamp_iso=timestamp_iso,
                memory_used_mb=mem_used_mb,
                memory_limit_mb=mem_limit_mb,
                memory_percent=mem_percent,
                cpu_percent=cpu_percent,
            )

        return results

    def get_simulation_metrics(self) -> SimulationPrometheusMetrics | None:
        """Get simulation-level metrics from Prometheus.

        Returns:
            SimulationPrometheusMetrics, or None if active_trips query fails.
        """
        active_trips_results = self._query_prometheus("simulation_trips_active")
        if not active_trips_results:
            return None

        item = active_trips_results[0]
        if not isinstance(item, dict):
            return None
        value_pair = item.get("value", [])
        if not isinstance(value_pair, list) or len(value_pair) < 2:
            return None
        try:
            active_trips = float(str(value_pair[1]))
        except ValueError:
            return None

        throughput_results = self._query_prometheus("sum(rate(simulation_events_total[30s]))")
        throughput = 0.0
        if throughput_results:
            th_item = throughput_results[0]
            if isinstance(th_item, dict):
                th_value_pair = th_item.get("value", [])
                if isinstance(th_value_pair, list) and len(th_value_pair) >= 2:
                    try:
                        throughput = float(str(th_value_pair[1]))
                    except ValueError:
                        pass

        rtr: float | None = None
        rtr_results = self._query_prometheus("simulation_real_time_ratio")
        if rtr_results:
            rtr_item = rtr_results[0]
            if isinstance(rtr_item, dict):
                rtr_value_pair = rtr_item.get("value", [])
                if isinstance(rtr_value_pair, list) and len(rtr_value_pair) >= 2:
                    try:
                        rtr = float(str(rtr_value_pair[1]))
                    except ValueError:
                        pass

        speed_multiplier = 1
        speed_results = self._query_prometheus("simulation_speed_multiplier")
        if speed_results:
            sp_item = speed_results[0]
            if isinstance(sp_item, dict):
                sp_value_pair = sp_item.get("value", [])
                if isinstance(sp_value_pair, list) and len(sp_value_pair) >= 2:
                    try:
                        speed_multiplier = int(float(str(sp_value_pair[1])))
                    except ValueError:
                        pass

        return SimulationPrometheusMetrics(
            active_trips=active_trips,
            throughput_events_per_sec=throughput,
            speed_multiplier=speed_multiplier,
            real_time_ratio=rtr,
        )

    def get_health_latencies(self) -> dict[str, ServiceHealthSample] | None:
        """Get service health latencies from the simulation API.

        Health latencies are not exposed via Prometheus — this delegates to the
        /metrics/infrastructure REST endpoint, mirroring InfrastructureHealthCollector.

        Returns:
            Dict mapping service name to ServiceHealthSample, or None on error.
        """
        try:
            response = self._client.get(
                f"{self._base_url}/metrics/infrastructure",
                headers={"X-API-Key": self._api_key},
            )
            if response.status_code != 200:
                return None

            data: dict[str, object] = response.json()
            services = data.get("services", [])
            if not isinstance(services, list):
                return None

            result: dict[str, ServiceHealthSample] = {}
            for svc in services:
                if not isinstance(svc, dict):
                    continue
                name = svc.get("name", "")
                if not isinstance(name, str) or not name:
                    continue
                latency_ms = svc.get("latency_ms")
                result[name] = ServiceHealthSample(
                    name=name,
                    latency_ms=float(latency_ms) if latency_ms is not None else None,
                    status=str(svc.get("status", "unknown")),
                    message=str(svc["message"]) if svc.get("message") is not None else None,
                    threshold_degraded=(
                        float(svc["threshold_degraded"])
                        if svc.get("threshold_degraded") is not None
                        else None
                    ),
                    threshold_unhealthy=(
                        float(svc["threshold_unhealthy"])
                        if svc.get("threshold_unhealthy") is not None
                        else None
                    ),
                )
            return result

        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def is_available(self) -> bool:
        """Check if Prometheus is reachable and returning data."""
        result = self._query_prometheus("up")
        return len(result) > 0
