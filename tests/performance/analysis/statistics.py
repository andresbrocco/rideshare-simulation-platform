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


def summarize_scenario_stats(
    samples: list[dict[str, Any]],
    focus_containers: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a summary of scenario statistics.

    Args:
        samples: List of sample dicts.
        focus_containers: Containers to focus on (default: core services).

    Returns:
        Summary dict with key metrics.
    """
    if focus_containers is None:
        focus_containers = [
            "rideshare-simulation",
            "rideshare-kafka",
            "rideshare-redis",
            "rideshare-osrm",
        ]

    all_stats = calculate_all_container_stats(samples)

    summary: dict[str, Any] = {
        "total_samples": len(samples),
        "containers_sampled": len(all_stats),
        "focus_containers": {},
    }

    for container in focus_containers:
        if container in all_stats:
            stats = all_stats[container]
            slope = calculate_memory_slope(samples, container)
            summary["focus_containers"][container] = {
                "memory_mean_mb": round(stats.memory_mean, 1),
                "memory_max_mb": round(stats.memory_max, 1),
                "memory_p95_mb": round(stats.memory_p95, 1),
                "memory_limit_mb": round(stats.memory_limit_mb, 1),
                "cpu_mean_percent": round(stats.cpu_mean, 1),
                "cpu_max_percent": round(stats.cpu_max, 1),
                "memory_slope_mb_per_min": round(slope, 3) if slope is not None else None,
            }

    return summary
