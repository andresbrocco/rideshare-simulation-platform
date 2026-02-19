"""Structured findings and verdicts for performance test analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Severity levels for findings."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FindingCategory(Enum):
    """Categories of performance findings."""

    MEMORY_LEAK = "memory_leak"
    CPU_LEAK = "cpu_leak"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    HIGH_CPU_USAGE = "high_cpu_usage"
    OOM_EVENT = "oom_event"
    STRESS_THRESHOLD = "stress_threshold"
    GLOBAL_CPU_SATURATION = "global_cpu_saturation"
    SIMULATION_LAG = "simulation_lag"
    CONTAINER_FAILURE = "container_failure"


class OverallStatus(Enum):
    """Overall test verdict status."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass
class Finding:
    """A single performance finding or issue detected."""

    severity: Severity
    category: FindingCategory
    container: str
    message: str
    metric_value: float
    threshold: float
    scenario_name: str | None = None
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "container": self.container,
            "message": self.message,
            "metric_value": round(self.metric_value, 2),
            "threshold": round(self.threshold, 2),
            "scenario_name": self.scenario_name,
            "recommendation": self.recommendation,
        }


@dataclass
class AggregatedFinding:
    """Groups the same container+category across scenarios into a single finding."""

    severity: Severity
    category: FindingCategory
    container: str
    display_name: str
    worst_value: float
    worst_scenario: str
    threshold: float
    scenarios_exceeded: list[str]
    values_by_scenario: dict[str, float]
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "container": self.container,
            "display_name": self.display_name,
            "worst_value": round(self.worst_value, 2),
            "worst_scenario": self.worst_scenario,
            "threshold": round(self.threshold, 2),
            "scenarios_exceeded": self.scenarios_exceeded,
            "values_by_scenario": {k: round(v, 2) for k, v in self.values_by_scenario.items()},
            "recommendation": self.recommendation,
        }


def aggregate_findings(
    raw_findings: list[Finding], display_names: dict[str, str] | None = None
) -> list[AggregatedFinding]:
    """Aggregate raw findings by (container, category).

    Groups the same container+category across scenarios into a single finding,
    picking the worst severity and worst value per group.

    Args:
        raw_findings: List of raw Finding objects.
        display_names: Optional mapping of container name to display name.

    Returns:
        List of AggregatedFinding objects, sorted by severity (critical first).
    """
    if display_names is None:
        display_names = {}

    # Group by (container, category)
    groups: dict[tuple[str, FindingCategory], list[Finding]] = {}
    for finding in raw_findings:
        key = (finding.container, finding.category)
        groups.setdefault(key, []).append(finding)

    aggregated: list[AggregatedFinding] = []
    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}

    for (container, category), findings in groups.items():
        # Pick worst severity
        worst_severity = min(findings, key=lambda f: severity_order[f.severity]).severity

        # Pick worst value and scenario
        worst_finding = max(findings, key=lambda f: f.metric_value)
        worst_value = worst_finding.metric_value
        worst_scenario = worst_finding.scenario_name or "unknown"

        # Collect scenarios that exceeded threshold
        scenarios_exceeded = sorted({f.scenario_name or "unknown" for f in findings})

        # Values by scenario
        values_by_scenario: dict[str, float] = {}
        for f in findings:
            scenario = f.scenario_name or "unknown"
            # Keep worst value per scenario
            if scenario not in values_by_scenario or f.metric_value > values_by_scenario[scenario]:
                values_by_scenario[scenario] = f.metric_value

        # Use the first finding's threshold (should be same for same container+category)
        threshold = findings[0].threshold

        # Generate contextual recommendation
        dn = display_names.get(container, container)
        total_scenarios = len(scenarios_exceeded)
        recommendation = _build_aggregated_recommendation(
            category, dn, worst_value, worst_scenario, total_scenarios, threshold
        )

        aggregated.append(
            AggregatedFinding(
                severity=worst_severity,
                category=category,
                container=container,
                display_name=dn,
                worst_value=worst_value,
                worst_scenario=worst_scenario,
                threshold=threshold,
                scenarios_exceeded=scenarios_exceeded,
                values_by_scenario=values_by_scenario,
                recommendation=recommendation,
            )
        )

    # Sort: critical first, then warning, then info; within same severity by worst_value desc
    aggregated.sort(key=lambda a: (severity_order[a.severity], -a.worst_value))
    return aggregated


def _build_aggregated_recommendation(
    category: FindingCategory,
    display_name: str,
    worst_value: float,
    worst_scenario: str,
    total_scenarios: int,
    threshold: float,
) -> str:
    """Build a contextual recommendation for an aggregated finding."""
    scenario_suffix = (
        f"exceeded {threshold:.0f}% threshold in {total_scenarios} scenario(s)"
        if total_scenarios > 1
        else f"exceeded {threshold:.0f}% threshold in {worst_scenario}"
    )

    if category == FindingCategory.HIGH_CPU_USAGE:
        return (
            f"{display_name} CPU peaked at {worst_value:.1f}% ({worst_scenario}); "
            f"{scenario_suffix}"
        )
    elif category == FindingCategory.HIGH_MEMORY_USAGE:
        return (
            f"{display_name} memory at {worst_value:.1f}% of limit ({worst_scenario}); "
            f"{scenario_suffix}"
        )
    elif category == FindingCategory.MEMORY_LEAK:
        return (
            f"{display_name} leaking at {worst_value:.2f} MB/min ({worst_scenario}); "
            "profile memory allocation and check for leaks"
        )
    elif category == FindingCategory.SIMULATION_LAG:
        return (
            f"{display_name} RTR peak {worst_value:.2f}x ({worst_scenario}); "
            "reduce agent count, lower speed multiplier, or optimize sim logic"
        )
    elif category == FindingCategory.OOM_EVENT:
        return (
            f"{display_name} hit OOM ({worst_scenario}); "
            "increase memory limit or optimize memory usage"
        )
    elif category == FindingCategory.GLOBAL_CPU_SATURATION:
        return (
            f"Global CPU at {worst_value:.1f}% of capacity ({worst_scenario}); "
            "system is CPU-saturated"
        )
    elif category == FindingCategory.CONTAINER_FAILURE:
        return f"{display_name} crashed ({worst_scenario}); check Docker logs"
    else:
        return f"{display_name}: {worst_value:.1f} ({worst_scenario}); {scenario_suffix}"


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
    status: str  # "healthy", "warning", "critical"

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
            "status": self.status,
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
    status: str  # "healthy", "warning", "critical"

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
            "status": self.status,
        }


@dataclass
class KeyMetrics:
    """Hero numbers for reports."""

    max_agents_queued: int | None
    max_speed_achieved: int | None
    leak_containers: list[str]
    rtr_peak: float | None
    stress_trigger: str | None
    total_duration_str: str
    available_cores: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "max_agents_queued": self.max_agents_queued,
            "max_speed_achieved": self.max_speed_achieved,
            "leak_containers": self.leak_containers,
            "rtr_peak": round(self.rtr_peak, 2) if self.rtr_peak is not None else None,
            "stress_trigger": self.stress_trigger,
            "total_duration_str": self.total_duration_str,
            "available_cores": self.available_cores,
        }


@dataclass
class TestVerdict:
    """Overall test verdict with findings and recommendations."""

    overall_status: OverallStatus
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    container_health: list[ContainerHealth] = field(default_factory=list)
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    total_oom_events: int = 0
    # New aggregated fields
    aggregated_findings: list[AggregatedFinding] = field(default_factory=list)
    aggregated_container_health: list[ContainerHealthAggregated] = field(default_factory=list)
    key_metrics: KeyMetrics | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "overall_status": self.overall_status.value,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": self.recommendations,
            "container_health": [c.to_dict() for c in self.container_health],
            "scenarios_passed": self.scenarios_passed,
            "scenarios_failed": self.scenarios_failed,
            "total_oom_events": self.total_oom_events,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
        }
        if self.aggregated_findings:
            result["aggregated_findings"] = [a.to_dict() for a in self.aggregated_findings]
        if self.aggregated_container_health:
            result["aggregated_container_health"] = [
                c.to_dict() for c in self.aggregated_container_health
            ]
        if self.key_metrics is not None:
            result["key_metrics"] = self.key_metrics.to_dict()
        return result

    @property
    def critical_count(self) -> int:
        """Count of critical findings."""
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        """Count of warning findings."""
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def aggregated_critical_count(self) -> int:
        """Count of critical aggregated findings."""
        return sum(1 for f in self.aggregated_findings if f.severity == Severity.CRITICAL)

    @property
    def aggregated_warning_count(self) -> int:
        """Count of warning aggregated findings."""
        return sum(1 for f in self.aggregated_findings if f.severity == Severity.WARNING)
