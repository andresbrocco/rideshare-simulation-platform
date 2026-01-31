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
    RESET_FAILURE = "reset_failure"
    OOM_EVENT = "oom_event"
    STRESS_THRESHOLD = "stress_threshold"
    SCALING_CONCERN = "scaling_concern"


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
class TestVerdict:
    """Overall test verdict with findings and recommendations."""

    overall_status: OverallStatus
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    container_health: list[ContainerHealth] = field(default_factory=list)
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    total_oom_events: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
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

    @property
    def critical_count(self) -> int:
        """Count of critical findings."""
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        """Count of warning findings."""
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)
