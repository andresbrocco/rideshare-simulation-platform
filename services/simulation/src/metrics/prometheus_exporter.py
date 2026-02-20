"""OpenTelemetry metrics exporter for simulation service.

Exports simulation metrics via OTLP to the OpenTelemetry Collector, which
forwards them to Prometheus via remote_write. Metric names are preserved
from the original prometheus_client implementation for Grafana dashboard
compatibility.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from opentelemetry import metrics
from opentelemetry.metrics import Observation

if TYPE_CHECKING:

    from metrics.collector import PerformanceSnapshot

# ---------------------------------------------------------------------------
# Meter
# ---------------------------------------------------------------------------
meter = metrics.get_meter("simulation")

# ---------------------------------------------------------------------------
# Counters (cumulative values)
# ---------------------------------------------------------------------------
simulation_events_total = meter.create_counter(
    name="simulation_events_total",
    description="Total events emitted by type",
    unit="1",
)

simulation_trips_completed_total = meter.create_counter(
    name="simulation_trips_completed_total",
    description="Total number of completed trips",
    unit="1",
)

simulation_trips_cancelled_total = meter.create_counter(
    name="simulation_trips_cancelled_total",
    description="Total number of cancelled trips",
    unit="1",
)

simulation_errors_total = meter.create_counter(
    name="simulation_errors_total",
    description="Total errors by component and type",
    unit="1",
)

simulation_corrupted_events_total = meter.create_counter(
    name="simulation_corrupted_events_total",
    description="Total corrupted events injected by corruption type",
    unit="1",
)

# ---------------------------------------------------------------------------
# UpDownCounters (mutable counts that can go up or down)
# ---------------------------------------------------------------------------
simulation_drivers_available = meter.create_up_down_counter(
    name="simulation_drivers_available",
    description="Number of drivers currently available for trips",
)

simulation_riders_awaiting_pickup = meter.create_up_down_counter(
    name="simulation_riders_awaiting_pickup",
    description="Number of riders waiting at pickup location for their driver",
)

simulation_riders_in_transit = meter.create_up_down_counter(
    name="simulation_riders_in_transit",
    description="Number of riders currently in transit",
)

simulation_trips_active = meter.create_up_down_counter(
    name="simulation_trips_active",
    description="Number of active trips",
)

# NOTE: offers_pending uses an Observable Gauge (not UpDownCounter) because
# offers are created and resolved within the same SimPy tick - the delta is
# always 0 between 1-second polling intervals. The gauge always emits the
# current instantaneous count at each OTel export interval.
simulation_offers_pending = meter.create_observable_gauge(
    name="simulation_offers_pending",
    callbacks=[lambda options: _observe("pending_offers")],
    description="Number of pending trip offers",
)

simulation_simpy_events = meter.create_up_down_counter(
    name="simulation_simpy_events",
    description="Number of events in SimPy queue",
)

# ---------------------------------------------------------------------------
# Observable Gauges (values polled via callbacks from snapshot)
# ---------------------------------------------------------------------------

# Thread-safe container for the latest snapshot values so that OTel
# callbacks can read them without holding a lock for too long.
_snapshot_lock = threading.Lock()
_snapshot_values: dict[str, float] = {
    "avg_fare": 0.0,
    "avg_duration_minutes": 0.0,
    "avg_match_seconds": 0.0,
    "avg_pickup_seconds": 0.0,
    "matching_success_rate": 0.0,
    "pending_offers": 0.0,
    "memory_rss_mb": 0.0,
    "memory_percent": 0.0,
    "cpu_percent": 0.0,
    "thread_count": 0.0,
}


def _observe(key: str) -> list[Observation]:
    """Return a single observation for the given snapshot key."""
    with _snapshot_lock:
        return [Observation(value=_snapshot_values.get(key, 0.0))]


simulation_avg_fare = meter.create_observable_gauge(
    name="simulation_avg_fare_dollars",
    callbacks=[lambda options: _observe("avg_fare")],
    description="Average trip fare in dollars",
)

simulation_avg_duration = meter.create_observable_gauge(
    name="simulation_avg_duration_minutes",
    callbacks=[lambda options: _observe("avg_duration_minutes")],
    description="Average trip duration in minutes",
    unit="min",
)

simulation_avg_match = meter.create_observable_gauge(
    name="simulation_avg_match_seconds",
    callbacks=[lambda options: _observe("avg_match_seconds")],
    description="Average time from request to driver match in seconds",
    unit="s",
)

simulation_avg_pickup = meter.create_observable_gauge(
    name="simulation_avg_pickup_seconds",
    callbacks=[lambda options: _observe("avg_pickup_seconds")],
    description="Average pickup time in seconds",
    unit="s",
)

simulation_matching_success_rate = meter.create_observable_gauge(
    name="simulation_matching_success_rate_percent",
    callbacks=[lambda options: _observe("matching_success_rate")],
    description="Matching success rate as a percentage",
    unit="%",
)

simulation_memory_rss_mb = meter.create_observable_gauge(
    name="simulation_memory_rss_mb",
    callbacks=[lambda options: _observe("memory_rss_mb")],
    description="Resident set size memory in MB",
)

simulation_memory_percent = meter.create_observable_gauge(
    name="simulation_memory_percent",
    callbacks=[lambda options: _observe("memory_percent")],
    description="Memory usage as percentage of system memory",
    unit="%",
)

simulation_cpu_percent = meter.create_observable_gauge(
    name="simulation_cpu_percent",
    callbacks=[lambda options: _observe("cpu_percent")],
    description="CPU usage percentage",
    unit="%",
)

simulation_thread_count = meter.create_observable_gauge(
    name="simulation_thread_count",
    callbacks=[lambda options: _observe("thread_count")],
    description="Number of active threads",
)

# ---------------------------------------------------------------------------
# Histograms (latency distributions)
# ---------------------------------------------------------------------------
simulation_osrm_latency_seconds = meter.create_histogram(
    name="simulation_osrm_latency_seconds",
    description="OSRM routing request latency in seconds",
    unit="s",
)

simulation_kafka_latency_seconds = meter.create_histogram(
    name="simulation_kafka_latency_seconds",
    description="Kafka publish latency in seconds",
    unit="s",
)

simulation_redis_latency_seconds = meter.create_histogram(
    name="simulation_redis_latency_seconds",
    description="Redis operation latency in seconds",
    unit="s",
)

# ---------------------------------------------------------------------------
# Previous counter tracking (for delta computation from cumulative inputs)
# ---------------------------------------------------------------------------
_previous_event_counts: dict[str, float] = {}
_previous_error_counts: dict[tuple[str, str], int] = {}
_previous_trips_completed: int = 0
_previous_trips_cancelled: int = 0
_previous_drivers_available: int = 0
_previous_riders_awaiting_pickup: int = 0
_previous_riders_in_transit: int = 0
_previous_active_trips: int = 0
_previous_simpy_events: int = 0


def update_metrics_from_snapshot(
    snapshot: PerformanceSnapshot,
    *,
    trips_completed: int = 0,
    trips_cancelled: int = 0,
    drivers_available: int = 0,
    riders_awaiting_pickup: int = 0,
    riders_in_transit: int = 0,
    active_trips: int = 0,
    avg_fare: float = 0.0,
    avg_duration_minutes: float = 0.0,
    avg_match_seconds: float = 0.0,
    avg_pickup_seconds: float = 0.0,
    matching_success_rate: float = 0.0,
    pending_offers: int = 0,
    simpy_events: int = 0,
) -> None:
    """Update OTel metrics from a MetricsCollector snapshot.

    For UpDownCounters, we compute the delta from the previous value so
    the counter tracks real-time state. For observable gauges the values
    are stored in the shared snapshot dict for callback reads.
    """
    global _previous_event_counts, _previous_error_counts
    global _previous_trips_completed, _previous_trips_cancelled
    global _previous_drivers_available, _previous_riders_awaiting_pickup, _previous_riders_in_transit
    global _previous_active_trips, _previous_simpy_events

    # --- Observable gauge values (stored for callback reads) ---
    with _snapshot_lock:
        _snapshot_values["avg_fare"] = avg_fare
        _snapshot_values["avg_duration_minutes"] = avg_duration_minutes
        _snapshot_values["avg_match_seconds"] = avg_match_seconds
        _snapshot_values["avg_pickup_seconds"] = avg_pickup_seconds
        _snapshot_values["matching_success_rate"] = matching_success_rate
        _snapshot_values["pending_offers"] = float(pending_offers)
        _snapshot_values["memory_rss_mb"] = snapshot.memory_rss_mb
        _snapshot_values["memory_percent"] = snapshot.memory_percent
        _snapshot_values["cpu_percent"] = snapshot.cpu_percent
        _snapshot_values["thread_count"] = float(snapshot.thread_count)

    # --- UpDownCounters (delta from previous to track real-time state) ---
    delta = drivers_available - _previous_drivers_available
    if delta != 0:
        simulation_drivers_available.add(delta)
    _previous_drivers_available = drivers_available

    delta = riders_awaiting_pickup - _previous_riders_awaiting_pickup
    if delta != 0:
        simulation_riders_awaiting_pickup.add(delta)
    _previous_riders_awaiting_pickup = riders_awaiting_pickup

    delta = riders_in_transit - _previous_riders_in_transit
    if delta != 0:
        simulation_riders_in_transit.add(delta)
    _previous_riders_in_transit = riders_in_transit

    delta = active_trips - _previous_active_trips
    if delta != 0:
        simulation_trips_active.add(delta)
    _previous_active_trips = active_trips

    delta = simpy_events - _previous_simpy_events
    if delta != 0:
        simulation_simpy_events.add(delta)
    _previous_simpy_events = simpy_events

    # --- Event counters (delta from rate * window) ---
    window_seconds = 60.0
    for event_type, rate in snapshot.events_per_second.items():
        estimated_count = rate * window_seconds
        prev_count = _previous_event_counts.get(event_type, 0.0)
        if estimated_count > prev_count:
            event_delta = estimated_count - prev_count
            simulation_events_total.add(event_delta, {"event_type": event_type})
        _previous_event_counts[event_type] = estimated_count

    # --- Trip counters ---
    if trips_completed > _previous_trips_completed:
        delta = trips_completed - _previous_trips_completed
        simulation_trips_completed_total.add(delta)
        _previous_trips_completed = trips_completed

    if trips_cancelled > _previous_trips_cancelled:
        delta = trips_cancelled - _previous_trips_cancelled
        simulation_trips_cancelled_total.add(delta)
        _previous_trips_cancelled = trips_cancelled

    # --- Error counters ---
    for component, error_stats in snapshot.errors.items():
        for error_type, count in error_stats.by_type.items():
            key = (component, error_type)
            prev = _previous_error_counts.get(key, 0)
            if count > prev:
                delta = count - prev
                simulation_errors_total.add(
                    delta, {"component": component, "error_type": error_type}
                )
            _previous_error_counts[key] = count


def observe_latency(component: str, latency_ms: float) -> None:
    """Observe a latency sample for histogram tracking.

    Args:
        component: One of "osrm", "kafka", "redis"
        latency_ms: Latency in milliseconds
    """
    latency_seconds = latency_ms / 1000.0

    if component == "osrm":
        simulation_osrm_latency_seconds.record(latency_seconds)
    elif component == "kafka":
        simulation_kafka_latency_seconds.record(latency_seconds)
    elif component == "redis":
        simulation_redis_latency_seconds.record(latency_seconds)


def record_corrupted_event(corruption_type: str) -> None:
    """Record a corrupted event injection for Prometheus tracking.

    Args:
        corruption_type: The corruption type value (e.g. "missing_required_field")
    """
    simulation_corrupted_events_total.add(1, {"corruption_type": corruption_type})
