"""Data models for performance test analysis — factual data only, no judgments."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContainerHealth:
    """Health summary for a single container."""

    container_name: str
    display_name: str
    memory_current_mb: float
    memory_limit_mb: float
    memory_percent: float
    memory_leak_rate_mb_per_min: float | None
    cpu_current_percent: float
    cpu_peak_percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "container_name": self.container_name,
            "display_name": self.display_name,
            "memory_current_mb": round(self.memory_current_mb, 1),
            "memory_limit_mb": round(self.memory_limit_mb, 1),
            "memory_percent": round(self.memory_percent, 1),
            "memory_leak_rate_mb_per_min": (
                round(self.memory_leak_rate_mb_per_min, 3)
                if self.memory_leak_rate_mb_per_min is not None
                else None
            ),
            "cpu_current_percent": round(self.cpu_current_percent, 1),
            "cpu_peak_percent": round(self.cpu_peak_percent, 1),
        }


@dataclass
class ContainerHealthAggregated:
    """Health summary aggregated across ALL scenarios."""

    container_name: str
    display_name: str
    memory_limit_mb: float
    baseline_memory_mb: float | None
    baseline_cpu_percent: float | None
    peak_memory_mb: float
    peak_memory_percent: float
    peak_memory_scenario: str
    peak_cpu_percent: float
    peak_cpu_scenario: str
    leak_rate_mb_per_min: float | None
    final_memory_mb: float
    final_memory_percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "container_name": self.container_name,
            "display_name": self.display_name,
            "memory_limit_mb": round(self.memory_limit_mb, 1),
            "baseline_memory_mb": (
                round(self.baseline_memory_mb, 1) if self.baseline_memory_mb is not None else None
            ),
            "baseline_cpu_percent": (
                round(self.baseline_cpu_percent, 1)
                if self.baseline_cpu_percent is not None
                else None
            ),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "peak_memory_percent": round(self.peak_memory_percent, 1),
            "peak_memory_scenario": self.peak_memory_scenario,
            "peak_cpu_percent": round(self.peak_cpu_percent, 1),
            "peak_cpu_scenario": self.peak_cpu_scenario,
            "leak_rate_mb_per_min": (
                round(self.leak_rate_mb_per_min, 3)
                if self.leak_rate_mb_per_min is not None
                else None
            ),
            "final_memory_mb": round(self.final_memory_mb, 1),
            "final_memory_percent": round(self.final_memory_percent, 1),
        }


@dataclass
class KeyMetrics:
    """Hero numbers for reports."""

    max_agents_queued: int | None
    max_speed_achieved: int | None
    leak_rates: dict[str, float]
    rtr_peak: float | None
    stress_trigger: str | None
    total_duration_str: str
    available_cores: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "max_agents_queued": self.max_agents_queued,
            "max_speed_achieved": self.max_speed_achieved,
            "leak_rates": {k: round(v, 3) for k, v in self.leak_rates.items()},
            "rtr_peak": round(self.rtr_peak, 2) if self.rtr_peak is not None else None,
            "stress_trigger": self.stress_trigger,
            "total_duration_str": self.total_duration_str,
            "available_cores": self.available_cores,
        }


@dataclass
class ServiceHealthLatency:
    """Health latency summary for a single service across scenarios."""

    service_name: str
    baseline_latency_p95: float | None
    stressed_latency_p95: float | None
    peak_latency_ms: float | None
    peak_latency_scenario: str | None
    threshold_degraded: float | None
    threshold_unhealthy: float | None
    threshold_source: str = "api-reported"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_name": self.service_name,
            "baseline_latency_p95": (
                round(self.baseline_latency_p95, 2)
                if self.baseline_latency_p95 is not None
                else None
            ),
            "stressed_latency_p95": (
                round(self.stressed_latency_p95, 2)
                if self.stressed_latency_p95 is not None
                else None
            ),
            "peak_latency_ms": (
                round(self.peak_latency_ms, 2) if self.peak_latency_ms is not None else None
            ),
            "peak_latency_scenario": self.peak_latency_scenario,
            "threshold_degraded": self.threshold_degraded,
            "threshold_unhealthy": self.threshold_unhealthy,
            "threshold_source": self.threshold_source,
        }


@dataclass
class SuggestedThresholds:
    """Empirically-derived threshold suggestions for a service."""

    service_name: str
    current_degraded: float | None
    current_unhealthy: float | None
    suggested_degraded: float
    suggested_unhealthy: float
    based_on_p95: float
    based_on_scenario: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_name": self.service_name,
            "current_degraded": self.current_degraded,
            "current_unhealthy": self.current_unhealthy,
            "suggested_degraded": self.suggested_degraded,
            "suggested_unhealthy": self.suggested_unhealthy,
            "based_on_p95": round(self.based_on_p95, 2),
            "based_on_scenario": self.based_on_scenario,
        }


@dataclass
class SaturationPoint:
    """A single observed (load, throughput) data point."""

    active_trips: float
    throughput: float  # effective throughput proxy
    speed_multiplier: int
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "active_trips": round(self.active_trips, 2),
            "throughput": round(self.throughput, 2),
            "speed_multiplier": self.speed_multiplier,
            "timestamp": self.timestamp,
        }


@dataclass
class USLFit:
    """Universal Scalability Law model fit results."""

    lambda_param: float  # throughput per unit load at N=1
    sigma_param: float  # contention coefficient [0,1]
    kappa_param: float  # coherency coefficient [0,1]
    r_squared: float  # goodness of fit
    n_star: float  # analytical peak: N* where dX/dN = 0
    x_max: float  # X(N*): predicted max throughput
    fit_successful: bool
    fit_message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "lambda_param": round(self.lambda_param, 6),
            "sigma_param": round(self.sigma_param, 6),
            "kappa_param": round(self.kappa_param, 6),
            "r_squared": round(self.r_squared, 4),
            "n_star": round(self.n_star, 2),
            "x_max": round(self.x_max, 2),
            "fit_successful": self.fit_successful,
            "fit_message": self.fit_message,
        }


@dataclass
class KneePoint:
    """Detected knee point in the saturation curve."""

    n_knee: float
    x_knee: float
    detection_method: str  # "usl_analytical" | "second_derivative" | "none"
    confidence: float  # [0, 1]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "n_knee": round(self.n_knee, 2),
            "x_knee": round(self.x_knee, 2),
            "detection_method": self.detection_method,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class SaturationCurve:
    """Saturation curve for a single speed multiplier."""

    speed_multiplier: int
    points: list[SaturationPoint]
    usl_fit: USLFit | None
    knee_point: KneePoint | None
    resource_bottleneck: str  # e.g. "rideshare-simulation", "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "speed_multiplier": self.speed_multiplier,
            "points": [p.to_dict() for p in self.points],
            "usl_fit": self.usl_fit.to_dict() if self.usl_fit is not None else None,
            "knee_point": self.knee_point.to_dict() if self.knee_point is not None else None,
            "resource_bottleneck": self.resource_bottleneck,
        }


@dataclass
class SaturationFamily:
    """Family of saturation curves across speed multipliers."""

    curves: list[SaturationCurve]
    best_n_star: float | None  # lowest N* across curves
    best_speed_multiplier: int | None  # speed at lowest N*

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "curves": [c.to_dict() for c in self.curves],
            "best_n_star": round(self.best_n_star, 2) if self.best_n_star is not None else None,
            "best_speed_multiplier": self.best_speed_multiplier,
        }


@dataclass
class TestSummary:
    """Factual summary of test results — no severity judgments."""

    container_health: list[ContainerHealth] = field(default_factory=list)
    aggregated_container_health: list[ContainerHealthAggregated] = field(default_factory=list)
    key_metrics: KeyMetrics | None = None
    service_health_latency: list[ServiceHealthLatency] = field(default_factory=list)
    suggested_thresholds: list[SuggestedThresholds] = field(default_factory=list)
    saturation_family: SaturationFamily | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "container_health": [c.to_dict() for c in self.container_health],
            "aggregated_container_health": [c.to_dict() for c in self.aggregated_container_health],
        }
        if self.key_metrics is not None:
            result["key_metrics"] = self.key_metrics.to_dict()
        if self.service_health_latency:
            result["service_health_latency"] = [s.to_dict() for s in self.service_health_latency]
        if self.suggested_thresholds:
            result["suggested_thresholds"] = [s.to_dict() for s in self.suggested_thresholds]
        if self.saturation_family is not None:
            result["saturation_family"] = self.saturation_family.to_dict()
        return result
