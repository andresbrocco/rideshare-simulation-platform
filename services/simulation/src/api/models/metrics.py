from enum import Enum

from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    total_drivers: int
    online_drivers: int
    total_riders: int
    waiting_riders: int
    in_transit_riders: int
    active_trips: int
    completed_trips_today: int


class ZoneMetrics(BaseModel):
    zone_id: str
    zone_name: str
    online_drivers: int
    waiting_riders: int
    active_trips: int
    surge_multiplier: float


class TripMetrics(BaseModel):
    active_trips: int
    completed_today: int
    cancelled_today: int
    avg_fare: float
    avg_duration_minutes: float
    avg_wait_seconds: float = 0.0  # Time from request to match
    avg_pickup_seconds: float = 0.0  # Time from match to driver arrival
    # Matching metrics
    offers_sent: int = 0
    offers_accepted: int = 0
    offers_rejected: int = 0
    offers_expired: int = 0
    matching_success_rate: float = 0.0  # Percentage


class DriverMetrics(BaseModel):
    online: int
    offline: int
    en_route_pickup: int
    en_route_destination: int
    total: int


class RiderMetrics(BaseModel):
    offline: int
    to_pickup: int
    in_transit: int
    total: int


class LatencyMetrics(BaseModel):
    avg_ms: float
    p95_ms: float
    p99_ms: float
    count: int


class EventsMetrics(BaseModel):
    gps_pings_per_sec: float
    trip_events_per_sec: float
    driver_status_per_sec: float
    total_per_sec: float


class LatencySummary(BaseModel):
    osrm: LatencyMetrics | None = None
    kafka: LatencyMetrics | None = None
    redis: LatencyMetrics | None = None


class ErrorStats(BaseModel):
    count: int = 0
    per_second: float = 0.0
    by_type: dict[str, int] = {}


class ErrorSummary(BaseModel):
    osrm: ErrorStats | None = None
    kafka: ErrorStats | None = None
    redis: ErrorStats | None = None


class QueueDepths(BaseModel):
    pending_offers: int = 0
    simpy_events: int = 0


class ResourceMetrics(BaseModel):
    memory_rss_mb: float
    memory_percent: float
    cpu_percent: float = 0.0
    thread_count: int = 0


class MemoryMetrics(BaseModel):
    rss_mb: float
    percent: float


class StreamProcessorLatency(BaseModel):
    """Stream processor latency metrics."""

    avg_ms: float
    p95_ms: float
    count: int


class StreamProcessorMetrics(BaseModel):
    """Stream processor performance metrics."""

    messages_consumed_per_sec: float
    messages_published_per_sec: float
    gps_aggregation_ratio: float
    redis_publish_latency: StreamProcessorLatency
    publish_errors_per_sec: float
    kafka_connected: bool
    redis_connected: bool
    uptime_seconds: float


class PerformanceMetrics(BaseModel):
    events: EventsMetrics
    latency: LatencySummary
    errors: ErrorSummary = ErrorSummary()
    queue_depths: QueueDepths
    memory: MemoryMetrics
    resources: ResourceMetrics | None = None
    stream_processor: StreamProcessorMetrics | None = None
    timestamp: float


class ContainerStatus(str, Enum):
    """Container health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class ServiceMetrics(BaseModel):
    """Unified metrics for a single service/container."""

    name: str  # Display name (e.g., "Kafka", "Redis")
    status: ContainerStatus
    latency_ms: float | None = None  # Health check latency
    message: str | None = None  # Status message
    memory_used_mb: float = 0.0
    memory_limit_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0


class InfrastructureResponse(BaseModel):
    """Response containing all service infrastructure metrics."""

    services: list[ServiceMetrics]
    overall_status: ContainerStatus
    cadvisor_available: bool
    timestamp: float
    # System-wide totals (normalized by total cores)
    total_cpu_percent: float = 0.0  # Normalized by total cores
    total_memory_used_mb: float = 0.0
    total_memory_capacity_mb: float = 0.0  # From cAdvisor machine info
    total_memory_percent: float = 0.0
    total_cores: int = 1  # Auto-detected from cAdvisor
    discovery_error: str | None = None  # Error message if compose.yml parsing failed
