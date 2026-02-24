"""Statistical analysis for performance test results."""

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ContainerStats:
    """Statistical summary for a container's metrics."""

    container_name: str
    sample_count: int
    # Memory stats (MB)
    memory_mean: float
    memory_std: float
    memory_min: float
    memory_max: float
    memory_p50: float
    memory_p95: float
    memory_p99: float
    memory_limit_mb: float
    # CPU stats (%)
    cpu_mean: float
    cpu_std: float
    cpu_min: float
    cpu_max: float
    cpu_p50: float
    cpu_p95: float
    cpu_p99: float


@dataclass
class HealthLatencyStats:
    """Statistical summary for a service's health check latency."""

    service_name: str
    sample_count: int
    latency_mean: float
    latency_std: float
    latency_min: float
    latency_max: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    threshold_degraded: float | None
    threshold_unhealthy: float | None


def calculate_health_stats(
    samples: list[dict[str, Any]],
    service_name: str,
) -> HealthLatencyStats | None:
    """Calculate latency statistics for a service from samples.

    Args:
        samples: List of sample dicts with optional 'health' key.
        service_name: Display name of the service to analyze.

    Returns:
        HealthLatencyStats with calculated statistics, or None if no data.
    """
    latency_values: list[float] = []
    threshold_degraded: float | None = None
    threshold_unhealthy: float | None = None

    for sample in samples:
        health = sample.get("health", {})
        svc_data = health.get(service_name)
        if svc_data is None:
            continue
        latency = svc_data.get("latency_ms")
        if latency is not None and isinstance(latency, (int, float)):
            latency_values.append(float(latency))
        # Capture thresholds from the first sample that has them
        if threshold_degraded is None and svc_data.get("threshold_degraded") is not None:
            threshold_degraded = svc_data["threshold_degraded"]
        if threshold_unhealthy is None and svc_data.get("threshold_unhealthy") is not None:
            threshold_unhealthy = svc_data["threshold_unhealthy"]

    if not latency_values:
        return None

    arr = np.array(latency_values)

    return HealthLatencyStats(
        service_name=service_name,
        sample_count=len(latency_values),
        latency_mean=float(np.mean(arr)),
        latency_std=float(np.std(arr)),
        latency_min=float(np.min(arr)),
        latency_max=float(np.max(arr)),
        latency_p50=float(np.percentile(arr, 50)),
        latency_p95=float(np.percentile(arr, 95)),
        latency_p99=float(np.percentile(arr, 99)),
        threshold_degraded=threshold_degraded,
        threshold_unhealthy=threshold_unhealthy,
    )


def calculate_all_health_stats(
    samples: list[dict[str, Any]],
) -> dict[str, HealthLatencyStats]:
    """Calculate latency statistics for all services in samples.

    Args:
        samples: List of sample dicts.

    Returns:
        Dict mapping service display name to HealthLatencyStats.
    """
    service_names: set[str] = set()
    for sample in samples:
        health = sample.get("health", {})
        service_names.update(health.keys())

    results: dict[str, HealthLatencyStats] = {}
    for name in service_names:
        stats = calculate_health_stats(samples, name)
        if stats is not None:
            results[name] = stats

    return results


def calculate_stats(
    samples: list[dict[str, Any]],
    container_name: str,
) -> ContainerStats | None:
    """Calculate statistics for a container from samples.

    Args:
        samples: List of sample dicts with 'containers' key.
        container_name: Name of the container to analyze.

    Returns:
        ContainerStats with calculated statistics, or None if no data.
    """
    memory_values: list[float] = []
    cpu_values: list[float] = []
    memory_limit: float = 0.0

    for sample in samples:
        containers = sample.get("containers", {})
        if container_name in containers:
            data = containers[container_name]
            memory_values.append(data["memory_used_mb"])
            cpu_values.append(data["cpu_percent"])
            if data["memory_limit_mb"] > 0:
                memory_limit = data["memory_limit_mb"]

    if not memory_values:
        return None

    memory_arr = np.array(memory_values)
    cpu_arr = np.array(cpu_values)

    return ContainerStats(
        container_name=container_name,
        sample_count=len(memory_values),
        # Memory stats
        memory_mean=float(np.mean(memory_arr)),
        memory_std=float(np.std(memory_arr)),
        memory_min=float(np.min(memory_arr)),
        memory_max=float(np.max(memory_arr)),
        memory_p50=float(np.percentile(memory_arr, 50)),
        memory_p95=float(np.percentile(memory_arr, 95)),
        memory_p99=float(np.percentile(memory_arr, 99)),
        memory_limit_mb=memory_limit,
        # CPU stats
        cpu_mean=float(np.mean(cpu_arr)),
        cpu_std=float(np.std(cpu_arr)),
        cpu_min=float(np.min(cpu_arr)),
        cpu_max=float(np.max(cpu_arr)),
        cpu_p50=float(np.percentile(cpu_arr, 50)),
        cpu_p95=float(np.percentile(cpu_arr, 95)),
        cpu_p99=float(np.percentile(cpu_arr, 99)),
    )


def calculate_all_container_stats(
    samples: list[dict[str, Any]],
) -> dict[str, ContainerStats]:
    """Calculate statistics for all containers in samples.

    Args:
        samples: List of sample dicts.

    Returns:
        Dict mapping container name to ContainerStats.
    """
    # Find all containers
    container_names: set[str] = set()
    for sample in samples:
        containers = sample.get("containers", {})
        container_names.update(containers.keys())

    results: dict[str, ContainerStats] = {}
    for name in container_names:
        stats = calculate_stats(samples, name)
        if stats is not None:
            results[name] = stats

    return results


def calculate_memory_slope(
    samples: list[dict[str, Any]],
    container_name: str,
) -> float | None:
    """Calculate memory growth slope (MB/min) for a container.

    Args:
        samples: List of sample dicts.
        container_name: Container to analyze.

    Returns:
        Slope in MB/min, or None if insufficient data.
    """
    timestamps: list[float] = []
    memory_values: list[float] = []

    for sample in samples:
        containers = sample.get("containers", {})
        if container_name in containers:
            timestamps.append(sample["timestamp"])
            memory_values.append(containers[container_name]["memory_used_mb"])

    if len(timestamps) < 2:
        return None

    # Convert to numpy arrays
    t = np.array(timestamps)
    m = np.array(memory_values)

    # Normalize timestamps to start from 0
    t = t - t[0]

    # Convert to minutes
    t_minutes = t / 60.0

    # Linear regression: slope = cov(t, m) / var(t)
    if np.var(t_minutes) == 0:
        return 0.0

    slope = float(np.cov(t_minutes, m)[0, 1] / np.var(t_minutes))
    return slope


def calculate_cpu_slope(
    samples: list[dict[str, Any]],
    container_name: str,
) -> float | None:
    """Calculate CPU growth slope (percent/min) for a container.

    Args:
        samples: List of sample dicts.
        container_name: Container to analyze.

    Returns:
        Slope in percent/min, or None if insufficient data.
    """
    timestamps: list[float] = []
    cpu_values: list[float] = []

    for sample in samples:
        containers = sample.get("containers", {})
        if container_name in containers:
            timestamps.append(sample["timestamp"])
            cpu_values.append(containers[container_name]["cpu_percent"])

    if len(timestamps) < 2:
        return None

    # Convert to numpy arrays
    t = np.array(timestamps)
    c = np.array(cpu_values)

    # Normalize timestamps to start from 0
    t = t - t[0]

    # Convert to minutes
    t_minutes = t / 60.0

    # Linear regression: slope = cov(t, c) / var(t)
    if np.var(t_minutes) == 0:
        return 0.0

    slope = float(np.cov(t_minutes, c)[0, 1] / np.var(t_minutes))
    return slope


def calculate_all_container_slopes(
    samples: list[dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    """Calculate memory and CPU slopes for all containers.

    Args:
        samples: List of sample dicts.

    Returns:
        Dict mapping container name to {memory_slope, cpu_slope}.
    """
    # Find all containers
    container_names: set[str] = set()
    for sample in samples:
        containers = sample.get("containers", {})
        container_names.update(containers.keys())

    results: dict[str, dict[str, float | None]] = {}
    for name in container_names:
        memory_slope = calculate_memory_slope(samples, name)
        cpu_slope = calculate_cpu_slope(samples, name)
        results[name] = {
            "memory_slope_mb_per_min": memory_slope,
            "cpu_slope_percent_per_min": cpu_slope,
        }

    return results


def summarize_scenario_stats(
    samples: list[dict[str, Any]],
    focus_containers: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a summary of scenario statistics.

    Args:
        samples: List of sample dicts.
        focus_containers: Containers to include (None = all containers).

    Returns:
        Summary dict with key metrics.
    """
    all_stats = calculate_all_container_stats(samples)
    all_slopes = calculate_all_container_slopes(samples)

    # If no focus specified, use all containers
    containers_to_include = (
        focus_containers if focus_containers is not None else list(all_stats.keys())
    )

    summary: dict[str, Any] = {
        "total_samples": len(samples),
        "containers_sampled": len(all_stats),
        "containers": {},
    }

    for container in containers_to_include:
        if container in all_stats:
            stats = all_stats[container]
            slopes = all_slopes.get(container, {})
            memory_slope = slopes.get("memory_slope_mb_per_min")
            cpu_slope = slopes.get("cpu_slope_percent_per_min")
            summary["containers"][container] = {
                "memory_mean_mb": round(stats.memory_mean, 1),
                "memory_max_mb": round(stats.memory_max, 1),
                "memory_p95_mb": round(stats.memory_p95, 1),
                "memory_limit_mb": round(stats.memory_limit_mb, 1),
                "cpu_mean_percent": round(stats.cpu_mean, 1),
                "cpu_max_percent": round(stats.cpu_max, 1),
                "memory_slope_mb_per_min": (
                    round(memory_slope, 3) if memory_slope is not None else None
                ),
                "cpu_slope_percent_per_min": round(cpu_slope, 3) if cpu_slope is not None else None,
            }

    return summary
