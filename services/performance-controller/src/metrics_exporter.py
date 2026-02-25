"""OpenTelemetry metrics exporter for performance controller service.

Exports controller metrics via OTLP to the OpenTelemetry Collector,
which forwards them to Prometheus via remote_write. Metric names match
the expectations of the performance-engineering Grafana dashboard.
"""

from __future__ import annotations

import threading

from opentelemetry import metrics
from opentelemetry.metrics import Observation

# ---------------------------------------------------------------------------
# Meter
# ---------------------------------------------------------------------------
meter = metrics.get_meter("performance-controller")

# ---------------------------------------------------------------------------
# Thread-safe snapshot for observable gauges
# ---------------------------------------------------------------------------
_snapshot_lock = threading.Lock()
_snapshot_values: dict[str, float] = {
    "performance_index": 0.0,
    "target_speed_multiplier": 0.0,
    "mode": 0.0,
}


def _observe(key: str) -> list[Observation]:
    """Return a single observation for the given snapshot key."""
    with _snapshot_lock:
        return [Observation(value=_snapshot_values.get(key, 0.0))]


# ---------------------------------------------------------------------------
# Observable Gauges
# ---------------------------------------------------------------------------
controller_performance_index = meter.create_observable_gauge(
    name="controller_performance_index",
    callbacks=[lambda options: _observe("performance_index")],
    description="Composite performance index (0-1)",
    unit="1",
)

controller_target_speed_multiplier = meter.create_observable_gauge(
    name="controller_target_speed_multiplier",
    callbacks=[lambda options: _observe("target_speed_multiplier")],
    description="Current target speed multiplier set by controller",
    unit="1",
)

controller_mode = meter.create_observable_gauge(
    name="controller_mode",
    callbacks=[lambda options: _observe("mode")],
    description="Controller mode (0=off, 1=on)",
    unit="1",
)

# ---------------------------------------------------------------------------
# Counter
# ---------------------------------------------------------------------------
controller_adjustments_total = meter.create_counter(
    name="controller_adjustments_total",
    description="Total speed adjustments made by controller",
    unit="1",
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def update_snapshot(index: float, speed: float) -> None:
    """Update the performance index and speed in the observable snapshot."""
    with _snapshot_lock:
        _snapshot_values["performance_index"] = index
        _snapshot_values["target_speed_multiplier"] = speed


def update_mode(mode_on: bool) -> None:
    """Update the controller mode in the observable snapshot."""
    with _snapshot_lock:
        _snapshot_values["mode"] = 1.0 if mode_on else 0.0


def record_adjustment() -> None:
    """Increment the adjustment counter."""
    controller_adjustments_total.add(1)
