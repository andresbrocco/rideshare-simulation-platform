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
    "infrastructure_headroom": 0.0,
    "applied_speed": 0.0,
    "mode": 0.0,
    "error_integral": 0.0,
    "error_derivative": 0.0,
}


def _observe(key: str) -> list[Observation]:
    """Return a single observation for the given snapshot key."""
    with _snapshot_lock:
        return [Observation(value=_snapshot_values.get(key, 0.0))]


# ---------------------------------------------------------------------------
# Observable Gauges
# ---------------------------------------------------------------------------
controller_infrastructure_headroom = meter.create_observable_gauge(
    name="controller_infrastructure_headroom",
    callbacks=[lambda options: _observe("infrastructure_headroom")],
    description="Composite infrastructure headroom (0-1)",
    unit="1",
)

controller_applied_speed = meter.create_observable_gauge(
    name="controller_applied_speed",
    callbacks=[lambda options: _observe("applied_speed")],
    description="Current applied speed set by controller",
    unit="1",
)

controller_mode = meter.create_observable_gauge(
    name="controller_mode",
    callbacks=[lambda options: _observe("mode")],
    description="Controller mode (0=off, 1=on)",
    unit="1",
)

controller_error_integral = meter.create_observable_gauge(
    name="controller_error_integral",
    callbacks=[lambda options: _observe("error_integral")],
    description="PID error integral (accumulated error-seconds)",
    unit="1",
)

controller_error_derivative = meter.create_observable_gauge(
    name="controller_error_derivative",
    callbacks=[lambda options: _observe("error_derivative")],
    description="PID error derivative (rate of error change)",
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
    """Update the infrastructure headroom and speed in the observable snapshot."""
    with _snapshot_lock:
        _snapshot_values["infrastructure_headroom"] = index
        _snapshot_values["applied_speed"] = speed


def update_mode(mode_on: bool) -> None:
    """Update the controller mode in the observable snapshot."""
    with _snapshot_lock:
        _snapshot_values["mode"] = 1.0 if mode_on else 0.0


def update_pid_state(error_integral: float, error_derivative: float) -> None:
    """Update the PID state in the observable snapshot."""
    with _snapshot_lock:
        _snapshot_values["error_integral"] = error_integral
        _snapshot_values["error_derivative"] = error_derivative


def record_adjustment() -> None:
    """Increment the adjustment counter."""
    controller_adjustments_total.add(1)
