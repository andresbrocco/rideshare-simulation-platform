"""Statistical analysis for performance test results."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class BaselineCalibration:
    """Dynamic thresholds derived from baseline measurement."""

    health_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)
    """Per-service thresholds: {service: {degraded, unhealthy, baseline_p95}}."""
    rtr_mean: float | None = None
    rtr_threshold: float | None = None
    rtr_threshold_source: str = "config-fallback"
    health_threshold_source: str = "config-fallback"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "health_thresholds": {
                svc: {k: round(v, 2) for k, v in thresholds.items()}
                for svc, thresholds in self.health_thresholds.items()
            },
            "rtr_mean": round(self.rtr_mean, 4) if self.rtr_mean is not None else None,
            "rtr_threshold": (
                round(self.rtr_threshold, 4) if self.rtr_threshold is not None else None
            ),
            "rtr_threshold_source": self.rtr_threshold_source,
            "health_threshold_source": self.health_threshold_source,
        }


def compute_baseline_calibration(
    samples: list[dict[str, Any]],
    degraded_multiplier: float,
    unhealthy_multiplier: float,
    rtr_fraction: float,
    rtr_config_fallback: float,
) -> BaselineCalibration:
    """Derive dynamic stop-condition thresholds from baseline samples.

    Args:
        samples: Baseline scenario samples.
        degraded_multiplier: Multiply baseline p95 to get degraded threshold.
        unhealthy_multiplier: Multiply baseline p95 to get unhealthy threshold.
        rtr_fraction: Fraction of baseline RTR mean for the stop threshold.
        rtr_config_fallback: Absolute RTR threshold from config (used when no RTR data).

    Returns:
        BaselineCalibration with derived thresholds.
    """
    calibration = BaselineCalibration()

    # Health latency thresholds
    health_stats = calculate_all_health_stats(samples)
    if health_stats:
        calibration.health_threshold_source = "baseline-derived"
        for svc_name, stats in health_stats.items():
            calibration.health_thresholds[svc_name] = {
                "baseline_p95": stats.latency_p95,
                "degraded": round(stats.latency_p95 * degraded_multiplier, 2),
                "unhealthy": round(stats.latency_p95 * unhealthy_multiplier, 2),
            }

    # RTR threshold
    rtr_values: list[float] = []
    for sample in samples:
        rtr_data = sample.get("rtr")
        if rtr_data is not None and "rtr" in rtr_data:
            rtr_values.append(rtr_data["rtr"])

    if rtr_values:
        rtr_arr = np.array(rtr_values)
        calibration.rtr_mean = float(np.mean(rtr_arr))
        calibration.rtr_threshold = round(calibration.rtr_mean * rtr_fraction, 4)
        calibration.rtr_threshold_source = "baseline-derived"
    else:
        calibration.rtr_mean = None
        calibration.rtr_threshold = rtr_config_fallback
        calibration.rtr_threshold_source = "config-fallback"

    return calibration


# ---------------------------------------------------------------------------
# USL Model Fitting & Saturation Curve Analysis (DISABLED)
# ---------------------------------------------------------------------------

# def _usl_model(
#     n: NDArray[np.floating[Any]], lam: float, sigma: float, kappa: float
# ) -> NDArray[np.floating[Any]]:
#     """Universal Scalability Law: X(N) = λN / (1 + σ(N-1) + κN(N-1))."""
#     return (lam * n) / (1.0 + sigma * (n - 1.0) + kappa * n * (n - 1.0))
#
#
# def fit_usl_model(load: list[float], throughput: list[float]) -> USLFit:
#     """Fit the USL model to observed (load, throughput) data.
#
#     Args:
#         load: Active trip counts (independent variable).
#         throughput: Effective throughput values (dependent variable).
#
#     Returns:
#         USLFit with model parameters, R-squared, and analytical peak.
#     """
#     if len(load) < 3 or len(throughput) < 3:
#         return USLFit(
#             lambda_param=0.0,
#             sigma_param=0.0,
#             kappa_param=0.0,
#             r_squared=0.0,
#             n_star=0.0,
#             x_max=0.0,
#             fit_successful=False,
#             fit_message=f"Insufficient data points ({len(load)}, need >= 3)",
#         )
#
#     n_arr = np.array(load, dtype=np.float64)
#     x_arr = np.array(throughput, dtype=np.float64)
#
#     # Filter out zero/negative load values
#     mask = n_arr > 0
#     n_arr = n_arr[mask]
#     x_arr = x_arr[mask]
#
#     if len(n_arr) < 3:
#         return USLFit(
#             lambda_param=0.0,
#             sigma_param=0.0,
#             kappa_param=0.0,
#             r_squared=0.0,
#             n_star=0.0,
#             x_max=0.0,
#             fit_successful=False,
#             fit_message="Insufficient positive data points after filtering",
#         )
#
#     # Initial guess
#     first_load = max(n_arr[0], 1e-9)
#     p0 = [x_arr[0] / first_load, 0.1, 0.001]
#
#     try:
#         popt, _ = curve_fit(
#             _usl_model,
#             n_arr,
#             x_arr,
#             p0=p0,
#             bounds=([0.0, 0.0, 0.0], [np.inf, 1.0, 1.0]),
#             maxfev=10000,
#         )
#         lam, sigma, kappa = float(popt[0]), float(popt[1]), float(popt[2])
#
#         # R-squared
#         x_pred = _usl_model(n_arr, lam, sigma, kappa)
#         ss_res = float(np.sum((x_arr - x_pred) ** 2))
#         ss_tot = float(np.sum((x_arr - np.mean(x_arr)) ** 2))
#         r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
#
#         # Analytical peak: N* = sqrt((1 - sigma) / kappa) when kappa > 0
#         if kappa > 1e-12 and sigma < 1.0:
#             n_star = math.sqrt((1.0 - sigma) / kappa)
#         else:
#             # No coherency penalty — throughput increases monotonically
#             n_star = float(np.max(n_arr))
#
#         x_max = float(_usl_model(np.array([n_star]), lam, sigma, kappa)[0])
#
#         return USLFit(
#             lambda_param=lam,
#             sigma_param=sigma,
#             kappa_param=kappa,
#             r_squared=r_squared,
#             n_star=n_star,
#             x_max=x_max,
#             fit_successful=True,
#             fit_message="Converged",
#         )
#     except RuntimeError as e:
#         return USLFit(
#             lambda_param=0.0,
#             sigma_param=0.0,
#             kappa_param=0.0,
#             r_squared=0.0,
#             n_star=0.0,
#             x_max=0.0,
#             fit_successful=False,
#             fit_message=f"Curve fit failed: {e}",
#         )
#
#
# def detect_knee_point(
#     load: list[float], throughput: list[float], usl_fit: USLFit | None
# ) -> KneePoint:
#     """Detect the knee point in a saturation curve.
#
#     Primary: USL analytical N* when fit is good (R² >= 0.80).
#     Fallback: second derivative max curvature.
#
#     Args:
#         load: Active trip counts.
#         throughput: Throughput values.
#         usl_fit: USL fit results (may be None).
#
#     Returns:
#         KneePoint with detection method and confidence.
#     """
#     # Primary: USL analytical
#     if usl_fit is not None and usl_fit.fit_successful and usl_fit.r_squared >= 0.80:
#         return KneePoint(
#             n_knee=usl_fit.n_star,
#             x_knee=usl_fit.x_max,
#             detection_method="usl_analytical",
#             confidence=min(usl_fit.r_squared, 1.0),
#         )
#
#     # Fallback: second derivative
#     if len(load) >= 3 and len(throughput) >= 3:
#         n_arr = np.array(load, dtype=np.float64)
#         x_arr = np.array(throughput, dtype=np.float64)
#
#         # Sort by load
#         sort_idx = np.argsort(n_arr)
#         n_sorted = n_arr[sort_idx]
#         x_sorted = x_arr[sort_idx]
#
#         # Compute second derivative
#         dx = np.gradient(x_sorted, n_sorted)
#         d2x = np.gradient(dx, n_sorted)
#
#         # Find max negative curvature (where throughput bends down)
#         knee_idx = int(np.argmin(d2x))
#         confidence = 0.5 if abs(float(d2x[knee_idx])) > 1e-6 else 0.2
#
#         return KneePoint(
#             n_knee=float(n_sorted[knee_idx]),
#             x_knee=float(x_sorted[knee_idx]),
#             detection_method="second_derivative",
#             confidence=confidence,
#         )
#
#     return KneePoint(
#         n_knee=0.0,
#         x_knee=0.0,
#         detection_method="none",
#         confidence=0.0,
#     )
#
#
# def extract_saturation_points(
#     samples: list[dict[str, Any]], speed_multiplier: int
# ) -> list[SaturationPoint]:
#     """Extract (active_trips, throughput) data points from samples.
#
#     Prefers Prometheus-sourced throughput (simulation_events_total rate)
#     and active_trips when available. Falls back to the RTR-based proxy
#     (active_trips * rtr * speed_multiplier) for backward compatibility
#     with old results.json files.
#
#     Args:
#         samples: Sample dicts with rtr sub-dict.
#         speed_multiplier: Speed multiplier for this data set.
#
#     Returns:
#         List of SaturationPoint sorted by active_trips.
#     """
#     points: list[SaturationPoint] = []
#
#     for sample in samples:
#         # Prefer Prometheus-sourced metrics (new format)
#         if "throughput_events_per_sec" in sample and "active_trips" in sample:
#             active_trips_f = float(sample["active_trips"])
#             throughput_f = float(sample["throughput_events_per_sec"])
#             if active_trips_f > 0 and throughput_f > 0:
#                 points.append(
#                     SaturationPoint(
#                         active_trips=active_trips_f,
#                         throughput=throughput_f,
#                         speed_multiplier=speed_multiplier,
#                         timestamp=sample.get("timestamp", 0.0),
#                     )
#                 )
#             continue
#
#         # Fallback: RTR-based proxy (backward compat with old results.json)
#         rtr_data = sample.get("rtr")
#         if rtr_data is None:
#             continue
#
#         active_trips = rtr_data.get("active_trips")
#         rtr_value = rtr_data.get("rtr")
#
#         if active_trips is None or rtr_value is None:
#             continue
#
#         active_trips_f = float(active_trips)
#         if active_trips_f <= 0:
#             continue
#
#         throughput = active_trips_f * float(rtr_value) * speed_multiplier
#         points.append(
#             SaturationPoint(
#                 active_trips=active_trips_f,
#                 throughput=throughput,
#                 speed_multiplier=speed_multiplier,
#                 timestamp=sample.get("timestamp", 0.0),
#             )
#         )
#
#     # Sort by active_trips
#     points.sort(key=lambda p: p.active_trips)
#     return points
#
#
# def build_saturation_curve(
#     samples: list[dict[str, Any]], speed_multiplier: int
# ) -> SaturationCurve:
#     """Build a complete saturation curve from samples.
#
#     Extracts points, fits USL model, detects knee point, and
#     identifies the resource bottleneck.
#
#     Args:
#         samples: Sample dicts.
#         speed_multiplier: Speed multiplier for this dataset.
#
#     Returns:
#         SaturationCurve with fit results and knee point.
#     """
#     points = extract_saturation_points(samples, speed_multiplier)
#
#     load = [p.active_trips for p in points]
#     throughput = [p.throughput for p in points]
#
#     usl_fit = fit_usl_model(load, throughput)
#     knee_point = detect_knee_point(load, throughput, usl_fit)
#
#     # Identify bottleneck: container with highest peak CPU
#     peak_cpu: dict[str, float] = {}
#     for sample in samples:
#         for container_name, container_data in sample.get("containers", {}).items():
#             cpu = container_data.get("cpu_percent", 0.0)
#             if container_name not in peak_cpu or cpu > peak_cpu[container_name]:
#                 peak_cpu[container_name] = cpu
#
#     bottleneck = "unknown"
#     if peak_cpu:
#         bottleneck = max(peak_cpu, key=lambda k: peak_cpu[k])
#
#     return SaturationCurve(
#         speed_multiplier=speed_multiplier,
#         points=points,
#         usl_fit=usl_fit if usl_fit.fit_successful else None,
#         knee_point=knee_point if knee_point.detection_method != "none" else None,
#         resource_bottleneck=bottleneck,
#     )
