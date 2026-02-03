"""Prometheus metrics exporter for simulation service.

Exports simulation metrics in Prometheus format by bridging from
the existing MetricsCollector snapshots.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from metrics.collector import PerformanceSnapshot

# Use a separate registry to avoid default Python metrics
REGISTRY = CollectorRegistry()

# --- Gauges (point-in-time values) ---

# Agent counts
simulation_drivers_online = Gauge(
    "simulation_drivers_online",
    "Number of drivers currently online",
    registry=REGISTRY,
)

simulation_riders_in_transit = Gauge(
    "simulation_riders_in_transit",
    "Number of riders currently in transit",
    registry=REGISTRY,
)

simulation_trips_active = Gauge(
    "simulation_trips_active",
    "Number of active trips",
    registry=REGISTRY,
)

# Trip quality metrics
simulation_avg_fare = Gauge(
    "simulation_avg_fare_dollars",
    "Average trip fare in dollars",
    registry=REGISTRY,
)

simulation_avg_duration = Gauge(
    "simulation_avg_duration_minutes",
    "Average trip duration in minutes",
    registry=REGISTRY,
)

simulation_avg_wait = Gauge(
    "simulation_avg_wait_seconds",
    "Average rider wait time in seconds",
    registry=REGISTRY,
)

simulation_avg_pickup = Gauge(
    "simulation_avg_pickup_seconds",
    "Average pickup time in seconds",
    registry=REGISTRY,
)

# Matching metrics
simulation_matching_success_rate = Gauge(
    "simulation_matching_success_rate_percent",
    "Matching success rate as a percentage",
    registry=REGISTRY,
)

simulation_offers_pending = Gauge(
    "simulation_offers_pending",
    "Number of pending trip offers",
    registry=REGISTRY,
)

# Queue depths
simulation_simpy_events = Gauge(
    "simulation_simpy_events",
    "Number of events in SimPy queue",
    registry=REGISTRY,
)

# Resource metrics
simulation_memory_rss_mb = Gauge(
    "simulation_memory_rss_mb",
    "Resident set size memory in MB",
    registry=REGISTRY,
)

simulation_memory_percent = Gauge(
    "simulation_memory_percent",
    "Memory usage as percentage of system memory",
    registry=REGISTRY,
)

simulation_cpu_percent = Gauge(
    "simulation_cpu_percent",
    "CPU usage percentage",
    registry=REGISTRY,
)

simulation_thread_count = Gauge(
    "simulation_thread_count",
    "Number of active threads",
    registry=REGISTRY,
)

# --- Counters (cumulative values) ---

simulation_events_total = Counter(
    "simulation_events_total",
    "Total events emitted by type",
    ["event_type"],
    registry=REGISTRY,
)

simulation_trips_completed_total = Counter(
    "simulation_trips_completed_total",
    "Total number of completed trips",
    registry=REGISTRY,
)

simulation_trips_cancelled_total = Counter(
    "simulation_trips_cancelled_total",
    "Total number of cancelled trips",
    registry=REGISTRY,
)

simulation_errors_total = Counter(
    "simulation_errors_total",
    "Total errors by component and type",
    ["component", "error_type"],
    registry=REGISTRY,
)

# --- Histograms (latency distributions) ---

# Bucket definitions based on observed latency ranges
OSRM_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, float("inf"))
KAFKA_LATENCY_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, float("inf"))
REDIS_LATENCY_BUCKETS = (0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, float("inf"))

simulation_osrm_latency_seconds = Histogram(
    "simulation_osrm_latency_seconds",
    "OSRM routing request latency in seconds",
    buckets=OSRM_LATENCY_BUCKETS,
    registry=REGISTRY,
)

simulation_kafka_latency_seconds = Histogram(
    "simulation_kafka_latency_seconds",
    "Kafka publish latency in seconds",
    buckets=KAFKA_LATENCY_BUCKETS,
    registry=REGISTRY,
)

simulation_redis_latency_seconds = Histogram(
    "simulation_redis_latency_seconds",
    "Redis operation latency in seconds",
    buckets=REDIS_LATENCY_BUCKETS,
    registry=REGISTRY,
)

# Track previous counter values to compute deltas
_previous_event_counts: dict[str, float] = {}
_previous_error_counts: dict[tuple[str, str], int] = {}
_previous_trips_completed: int = 0
_previous_trips_cancelled: int = 0


def update_metrics_from_snapshot(
    snapshot: PerformanceSnapshot,
    *,
    trips_completed: int = 0,
    trips_cancelled: int = 0,
    drivers_online: int = 0,
    riders_in_transit: int = 0,
    active_trips: int = 0,
    avg_fare: float = 0.0,
    avg_duration_minutes: float = 0.0,
    avg_wait_seconds: float = 0.0,
    avg_pickup_seconds: float = 0.0,
    matching_success_rate: float = 0.0,
    pending_offers: int = 0,
    simpy_events: int = 0,
) -> None:
    """Update Prometheus metrics from a MetricsCollector snapshot.

    This bridges the existing collector data to Prometheus format.
    Call this before generating Prometheus output.

    Args:
        snapshot: Performance snapshot from MetricsCollector
        trips_completed: Total completed trips (cumulative)
        trips_cancelled: Total cancelled trips (cumulative)
        drivers_online: Current online driver count
        riders_in_transit: Current in-transit rider count
        active_trips: Current active trip count
        avg_fare: Average fare in dollars
        avg_duration_minutes: Average trip duration
        avg_wait_seconds: Average wait time
        avg_pickup_seconds: Average pickup time
        matching_success_rate: Success rate as percentage
        pending_offers: Number of pending offers
        simpy_events: SimPy event queue depth
    """
    global _previous_event_counts, _previous_error_counts
    global _previous_trips_completed, _previous_trips_cancelled

    # Update gauges
    simulation_drivers_online.set(drivers_online)
    simulation_riders_in_transit.set(riders_in_transit)
    simulation_trips_active.set(active_trips)

    simulation_avg_fare.set(avg_fare)
    simulation_avg_duration.set(avg_duration_minutes)
    simulation_avg_wait.set(avg_wait_seconds)
    simulation_avg_pickup.set(avg_pickup_seconds)

    simulation_matching_success_rate.set(matching_success_rate)
    simulation_offers_pending.set(pending_offers)
    simulation_simpy_events.set(simpy_events)

    simulation_memory_rss_mb.set(snapshot.memory_rss_mb)
    simulation_memory_percent.set(snapshot.memory_percent)
    simulation_cpu_percent.set(snapshot.cpu_percent)
    simulation_thread_count.set(snapshot.thread_count)

    # Update event counters (from rate * window_seconds approximation)
    # The collector tracks events per second, we need cumulative counts
    # We'll use the rate to estimate delta and increment
    window_seconds = 60.0  # Default collector window
    for event_type, rate in snapshot.events_per_second.items():
        # Estimate events in window
        estimated_count = rate * window_seconds
        prev_count = _previous_event_counts.get(event_type, 0.0)
        # Only increment if count increased
        if estimated_count > prev_count:
            delta = estimated_count - prev_count
            simulation_events_total.labels(event_type=event_type).inc(delta)
        _previous_event_counts[event_type] = estimated_count

    # Update trip counters
    if trips_completed > _previous_trips_completed:
        delta = trips_completed - _previous_trips_completed
        simulation_trips_completed_total.inc(delta)
        _previous_trips_completed = trips_completed

    if trips_cancelled > _previous_trips_cancelled:
        delta = trips_cancelled - _previous_trips_cancelled
        simulation_trips_cancelled_total.inc(delta)
        _previous_trips_cancelled = trips_cancelled

    # Update error counters
    for component, error_stats in snapshot.errors.items():
        for error_type, count in error_stats.by_type.items():
            key = (component, error_type)
            prev = _previous_error_counts.get(key, 0)
            if count > prev:
                delta = count - prev
                simulation_errors_total.labels(component=component, error_type=error_type).inc(
                    delta
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
        simulation_osrm_latency_seconds.observe(latency_seconds)
    elif component == "kafka":
        simulation_kafka_latency_seconds.observe(latency_seconds)
    elif component == "redis":
        simulation_redis_latency_seconds.observe(latency_seconds)


def generate_prometheus_metrics() -> bytes:
    """Generate Prometheus format metrics output.

    Returns:
        Prometheus text format as bytes
    """
    result: bytes = generate_latest(REGISTRY)
    return result
