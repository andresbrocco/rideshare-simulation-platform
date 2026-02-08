import functools
import logging
import pathlib
import time
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, cast

import httpx
from fastapi import APIRouter, Depends, Request

from api.auth import verify_api_key
from api.models.metrics import (
    ContainerStatus,
    DriverMetrics,
    ErrorStats,
    ErrorSummary,
    EventsMetrics,
    InfrastructureResponse,
    LatencyMetrics,
    LatencySummary,
    MemoryMetrics,
    OverviewMetrics,
    PerformanceMetrics,
    QueueDepths,
    ResourceMetrics,
    RiderMetrics,
    ServiceMetrics,
    StreamProcessorLatency,
    StreamProcessorMetrics,
    TripMetrics,
    ZoneMetrics,
)
from api.rate_limit import limiter
from metrics import get_metrics_collector
from trip import TripState

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

CACHE_TTL = 0.5  # 500ms for responsive updates
_metrics_cache: dict[str, Any] = {}

# Module-level cache for machine info (rarely changes)
_machine_info_cache: dict[str, Any] | None = None
_machine_info_cache_time: float = 0.0
MACHINE_INFO_CACHE_TTL = 300.0  # 5 minutes

T = TypeVar("T")


def get_engine(request: Request) -> Any:
    return request.app.state.engine


def get_driver_registry(request: Request) -> Any:
    if hasattr(request.app.state, "driver_registry"):
        return request.app.state.driver_registry
    return None


def get_matching_server(request: Request) -> Any:
    if hasattr(request.app.state, "matching_server"):
        return request.app.state.matching_server
    # Fallback to engine's matching server
    if hasattr(request.app.state, "engine") and hasattr(
        request.app.state.engine, "_matching_server"
    ):
        return request.app.state.engine._matching_server
    return None


EngineDep = Annotated[Any, Depends(get_engine)]
DriverRegistryDep = Annotated[Any, Depends(get_driver_registry)]
MatchingServerDep = Annotated[Any, Depends(get_matching_server)]


def _get_cached_or_compute(cache_key: str, compute_func: Callable[[], T]) -> T:
    now = time.time()
    if cache_key in _metrics_cache:
        entry = _metrics_cache[cache_key]
        if entry["expires_at"] > now:
            return cast(T, entry["data"])

    data = compute_func()
    _metrics_cache[cache_key] = {"data": data, "expires_at": now + CACHE_TTL}
    return data


@router.get("/overview", response_model=OverviewMetrics)
@limiter.limit("120/minute")
def get_overview_metrics(
    request: Request, engine: EngineDep, driver_registry: DriverRegistryDep
) -> OverviewMetrics:
    """Returns overview metrics with total counts."""

    def compute() -> OverviewMetrics:
        total_drivers = len(engine._active_drivers) if hasattr(engine, "_active_drivers") else 0
        total_riders = len(engine._active_riders) if hasattr(engine, "_active_riders") else 0

        online_drivers = 0
        if driver_registry:
            online_drivers = driver_registry.get_all_status_counts().get("online", 0)

        waiting_riders = sum(
            1
            for rider in (
                engine._active_riders.values() if hasattr(engine, "_active_riders") else []
            )
            if hasattr(rider, "status") and rider.status == "waiting"
        )

        in_transit_riders = sum(
            1
            for rider in (
                engine._active_riders.values() if hasattr(engine, "_active_riders") else []
            )
            if hasattr(rider, "status") and rider.status == "in_trip"
        )

        active_trips = 0
        if hasattr(engine, "_get_in_flight_trips"):
            active_trips = len(engine._get_in_flight_trips())

        # Get completed trips count from matching server
        completed_trips_today = 0
        if hasattr(engine, "_matching_server") and engine._matching_server:
            matching_server = engine._matching_server
            if hasattr(matching_server, "get_trip_stats"):
                stats = matching_server.get_trip_stats()
                completed_trips_today = stats.get("completed_count", 0)

        return OverviewMetrics(
            total_drivers=total_drivers,
            online_drivers=online_drivers,
            total_riders=total_riders,
            waiting_riders=waiting_riders,
            in_transit_riders=in_transit_riders,
            active_trips=active_trips,
            completed_trips_today=completed_trips_today,
        )

    return _get_cached_or_compute("overview", compute)


@router.get("/zones", response_model=list[ZoneMetrics])
@limiter.limit("120/minute")
def get_zone_metrics(
    request: Request, engine: EngineDep, driver_registry: DriverRegistryDep
) -> list[ZoneMetrics]:
    """Returns per-zone metrics with supply, demand, and surge."""

    def compute() -> list[ZoneMetrics]:
        zones: list[ZoneMetrics] = []
        zone_ids = ["zone_1", "zone_2", "zone_3"]

        for zone_id in zone_ids:
            online_drivers = 0
            if driver_registry:
                online_drivers = driver_registry.get_zone_driver_count(zone_id, "online")

            waiting_riders = 0
            if hasattr(engine, "_active_riders"):
                waiting_riders = sum(
                    1
                    for rider in engine._active_riders.values()
                    if hasattr(rider, "status")
                    and rider.status == "waiting"
                    and hasattr(rider, "current_zone_id")
                    and rider.current_zone_id == zone_id
                )

            zones.append(
                ZoneMetrics(
                    zone_id=zone_id,
                    zone_name=zone_id.replace("_", " ").title(),
                    online_drivers=online_drivers,
                    waiting_riders=waiting_riders,
                    active_trips=0,
                    surge_multiplier=1.0,
                )
            )

        return zones

    return _get_cached_or_compute("zones", compute)


@router.get("/trips", response_model=TripMetrics)
@limiter.limit("120/minute")
def get_trip_metrics(request: Request, engine: EngineDep) -> TripMetrics:
    """Returns trip statistics including active, completed, and averages."""

    def compute() -> TripMetrics:
        active_trips = 0
        if hasattr(engine, "_get_in_flight_trips"):
            active_trips = len(engine._get_in_flight_trips())

        # Get trip stats from matching server
        completed_today = 0
        cancelled_today = 0
        avg_fare = 0.0
        avg_duration_minutes = 0.0
        avg_wait_seconds = 0.0
        avg_pickup_seconds = 0.0

        # Matching stats
        offers_sent = 0
        offers_accepted = 0
        offers_rejected = 0
        offers_expired = 0
        matching_success_rate = 0.0

        if hasattr(engine, "_matching_server") and engine._matching_server:
            matching_server = engine._matching_server
            if hasattr(matching_server, "get_trip_stats"):
                stats = matching_server.get_trip_stats()
                completed_today = stats.get("completed_count", 0)
                cancelled_today = stats.get("cancelled_count", 0)
                avg_fare = stats.get("avg_fare", 0.0)
                avg_duration_minutes = stats.get("avg_duration_minutes", 0.0)
                avg_wait_seconds = stats.get("avg_wait_seconds", 0.0)
                avg_pickup_seconds = stats.get("avg_pickup_seconds", 0.0)

            # Get matching stats
            if hasattr(matching_server, "get_matching_stats"):
                matching_stats = matching_server.get_matching_stats()
                offers_sent = matching_stats.get("offers_sent", 0)
                offers_accepted = matching_stats.get("offers_accepted", 0)
                offers_rejected = matching_stats.get("offers_rejected", 0)
                offers_expired = matching_stats.get("offers_expired", 0)
                if offers_sent > 0:
                    matching_success_rate = (offers_accepted / offers_sent) * 100

        return TripMetrics(
            active_trips=active_trips,
            completed_today=completed_today,
            cancelled_today=cancelled_today,
            avg_fare=avg_fare,
            avg_duration_minutes=avg_duration_minutes,
            avg_wait_seconds=avg_wait_seconds,
            avg_pickup_seconds=avg_pickup_seconds,
            offers_sent=offers_sent,
            offers_accepted=offers_accepted,
            offers_rejected=offers_rejected,
            offers_expired=offers_expired,
            matching_success_rate=matching_success_rate,
        )

    return _get_cached_or_compute("trips", compute)


@router.get("/drivers", response_model=DriverMetrics)
@limiter.limit("120/minute")
def get_driver_metrics(request: Request, driver_registry: DriverRegistryDep) -> DriverMetrics:
    """Returns driver status counts."""

    def compute() -> DriverMetrics:
        if not driver_registry:
            return DriverMetrics(
                online=0,
                offline=0,
                en_route_pickup=0,
                en_route_destination=0,
                total=0,
            )

        status_counts = driver_registry.get_all_status_counts()
        online = status_counts.get("online", 0)
        offline = status_counts.get("offline", 0)
        en_route_pickup = status_counts.get("en_route_pickup", 0)
        en_route_destination = status_counts.get("en_route_destination", 0)
        total = online + offline + en_route_pickup + en_route_destination

        return DriverMetrics(
            online=online,
            offline=offline,
            en_route_pickup=en_route_pickup,
            en_route_destination=en_route_destination,
            total=total,
        )

    return _get_cached_or_compute("drivers", compute)


@router.get("/riders", response_model=RiderMetrics)
@limiter.limit("120/minute")
def get_rider_metrics(
    request: Request, engine: EngineDep, matching_server: MatchingServerDep
) -> RiderMetrics:
    """Returns rider status counts derived from trip states.

    Rider states:
    - offline: No active trip (includes matching phase - ephemeral states)
    - to_pickup: Trip state in (DRIVER_EN_ROUTE, DRIVER_ARRIVED)
    - in_transit: Trip state is STARTED

    Note: Matching phase states (REQUESTED, OFFER_SENT, MATCHED, etc.) are
    ephemeral and counted as offline since they transition too quickly to observe.
    """

    def compute() -> RiderMetrics:
        if not hasattr(engine, "_active_riders"):
            return RiderMetrics(offline=0, to_pickup=0, in_transit=0, total=0)

        # Build rider -> trip state map from active trips
        rider_trip_states: dict[str, TripState] = {}
        if matching_server and hasattr(matching_server, "get_active_trips"):
            for trip in matching_server.get_active_trips():
                rider_trip_states[trip.rider_id] = trip.state

        offline = to_pickup = in_transit = 0

        for rider in engine._active_riders.values():
            rider_id = getattr(rider, "rider_id", None)
            if not rider_id:
                continue

            trip_state = rider_trip_states.get(rider_id)

            if trip_state is None:
                # No active trip - rider is offline
                offline += 1
            elif trip_state in (
                TripState.REQUESTED,
                TripState.OFFER_SENT,
                TripState.OFFER_EXPIRED,
                TripState.OFFER_REJECTED,
                TripState.MATCHED,
            ):
                # Trip is in matching phase - ephemeral, count as offline
                offline += 1
            elif trip_state in (TripState.DRIVER_EN_ROUTE, TripState.DRIVER_ARRIVED):
                # Driver is heading to pickup or waiting
                to_pickup += 1
            elif trip_state == TripState.STARTED:
                # Rider is in vehicle
                in_transit += 1
            else:
                # COMPLETED or CANCELLED shouldn't be in active trips
                offline += 1

        total = offline + to_pickup + in_transit
        return RiderMetrics(
            offline=offline,
            to_pickup=to_pickup,
            in_transit=in_transit,
            total=total,
        )

    return _get_cached_or_compute("riders", compute)


def _fetch_stream_processor_metrics() -> StreamProcessorMetrics | None:
    """Fetch metrics from stream processor service.

    Returns None if the service is unavailable.
    """
    # Use internal Docker network URL
    stream_processor_url = "http://stream-processor:8080/metrics"

    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(stream_processor_url)
            if response.status_code == 200:
                data = response.json()
                return StreamProcessorMetrics(
                    messages_consumed_per_sec=data.get("messages_consumed_per_sec", 0.0),
                    messages_published_per_sec=data.get("messages_published_per_sec", 0.0),
                    gps_aggregation_ratio=data.get("gps_aggregation_ratio", 0.0),
                    redis_publish_latency=StreamProcessorLatency(
                        avg_ms=data.get("redis_publish_latency", {}).get("avg_ms", 0.0),
                        p95_ms=data.get("redis_publish_latency", {}).get("p95_ms", 0.0),
                        count=data.get("redis_publish_latency", {}).get("count", 0),
                    ),
                    publish_errors_per_sec=data.get("publish_errors_per_sec", 0.0),
                    kafka_connected=data.get("kafka_connected", False),
                    redis_connected=data.get("redis_connected", False),
                    uptime_seconds=data.get("uptime_seconds", 0.0),
                )
    except Exception as e:
        logger.debug(f"Failed to fetch stream processor metrics: {e}")

    return None


@router.get("/performance", response_model=PerformanceMetrics)
@limiter.limit("120/minute")
def get_performance_metrics(request: Request, engine: EngineDep) -> PerformanceMetrics:
    """Returns real-time performance metrics.

    Includes:
    - Event throughput (events per second by type)
    - Latency statistics (OSRM, Kafka, Redis)
    - Error statistics (OSRM, Kafka, Redis)
    - Queue depths (pending offers, simpy events)
    - Memory and CPU usage
    - Stream processor metrics (optional)
    """
    collector = get_metrics_collector()
    snapshot = collector.get_snapshot()

    # Build events metrics
    events = EventsMetrics(
        gps_pings_per_sec=snapshot.events_per_second.get("gps_ping", 0.0),
        trip_events_per_sec=snapshot.events_per_second.get("trip_event", 0.0),
        driver_status_per_sec=snapshot.events_per_second.get("driver_status", 0.0),
        total_per_sec=snapshot.total_events_per_second,
    )

    # Build latency metrics
    latency_summary = LatencySummary()
    for component in ["osrm", "kafka", "redis"]:
        if component in snapshot.latency:
            stats = snapshot.latency[component]
            latency_model = LatencyMetrics(
                avg_ms=stats.avg_ms,
                p95_ms=stats.p95_ms,
                p99_ms=stats.p99_ms,
                count=stats.count,
            )
            setattr(latency_summary, component, latency_model)

    # Build error metrics
    error_summary = ErrorSummary()
    for component in ["osrm", "kafka", "redis"]:
        if component in snapshot.errors:
            err_stats = snapshot.errors[component]
            error_model = ErrorStats(
                count=err_stats.count,
                per_second=err_stats.per_second,
                by_type=err_stats.by_type,
            )
            setattr(error_summary, component, error_model)

    # Get queue depths from engine
    pending_offers = 0
    simpy_events = 0

    # Get SimPy queue depth
    if hasattr(engine, "_env") and hasattr(engine._env, "_queue"):
        simpy_events = len(engine._env._queue)

    # Build resource metrics
    resources = ResourceMetrics(
        memory_rss_mb=snapshot.memory_rss_mb,
        memory_percent=snapshot.memory_percent,
        cpu_percent=snapshot.cpu_percent,
        thread_count=snapshot.thread_count,
    )

    # Fetch stream processor metrics (optional, may be None if unavailable)
    stream_processor_metrics = _fetch_stream_processor_metrics()

    return PerformanceMetrics(
        events=events,
        latency=latency_summary,
        errors=error_summary,
        queue_depths=QueueDepths(
            pending_offers=pending_offers,
            simpy_events=simpy_events,
        ),
        memory=MemoryMetrics(rss_mb=snapshot.memory_rss_mb, percent=snapshot.memory_percent),
        resources=resources,
        stream_processor=stream_processor_metrics,
        timestamp=snapshot.timestamp,
    )


COMPOSE_FILE_PATH = pathlib.Path("/app/compose.yml")

# Display name overrides for containers where auto-generation is insufficient
_DISPLAY_NAME_OVERRIDES: dict[str, str] = {
    "rideshare-osrm": "OSRM",
    "rideshare-minio": "MinIO",
    "rideshare-cadvisor": "cAdvisor",
    "rideshare-otel-collector": "OTel Collector",
    "rideshare-spark-thrift-server": "Spark Thrift",
    "rideshare-bronze-ingestion-high-volume": "Spark: High Volume",
    "rideshare-bronze-ingestion-low-volume": "Spark: Low Volume",
    "rideshare-postgres-airflow": "Postgres (Airflow)",
    "rideshare-postgres-metastore": "Postgres (Metastore)",
    "rideshare-airflow-webserver": "Airflow Web",
    "rideshare-localstack": "LocalStack",
}

# Minimal fallback used when compose.yml is missing or malformed
_FALLBACK_CONTAINER_CONFIG: dict[str, dict[str, str]] = {
    "rideshare-kafka": {"display_name": "Kafka"},
    "rideshare-redis": {"display_name": "Redis"},
    "rideshare-osrm": {"display_name": "OSRM"},
    "rideshare-simulation": {"display_name": "Simulation"},
    "rideshare-stream-processor": {"display_name": "Stream Processor"},
    "rideshare-frontend": {"display_name": "Frontend"},
    "rideshare-prometheus": {"display_name": "Prometheus"},
    "rideshare-grafana": {"display_name": "Grafana"},
}


def _generate_display_name(container_name: str) -> str:
    """Generate a display name from a container name.

    Strips the 'rideshare-' prefix, replaces hyphens with spaces, and title-cases.
    """
    name = container_name.removeprefix("rideshare-")
    return name.replace("-", " ").title()


@functools.cache
def _discover_containers() -> tuple[dict[str, dict[str, str]], str | None]:
    """Parse compose.yml to dynamically build the container configuration.

    Returns a tuple of (container_config, error_message).
    error_message is None on success, or a description of the problem on failure.
    """
    import yaml

    if not COMPOSE_FILE_PATH.exists():
        logger.warning("compose.yml not found at %s — using fallback", COMPOSE_FILE_PATH)
        return (
            _FALLBACK_CONTAINER_CONFIG,
            f"compose.yml not found at {COMPOSE_FILE_PATH} — showing fallback services",
        )

    try:
        raw = COMPOSE_FILE_PATH.read_text(encoding="utf-8")
        compose: dict[str, Any] = yaml.safe_load(raw)
    except Exception as exc:
        logger.warning("Failed to parse compose.yml: %s — using fallback", exc)
        return (
            _FALLBACK_CONTAINER_CONFIG,
            f"Failed to parse compose.yml: {exc} — showing fallback services",
        )

    services_section = compose.get("services")
    if not isinstance(services_section, dict):
        logger.warning("compose.yml has no 'services' section — using fallback")
        return (
            _FALLBACK_CONTAINER_CONFIG,
            "compose.yml has no 'services' section — showing fallback services",
        )

    config: dict[str, dict[str, str]] = {}
    project_name = compose.get("name", "rideshare-platform")
    # Docker Compose derives container_name from: explicit container_name > {project}-{service}-1
    # We handle both cases.
    for service_name, service_def in services_section.items():
        if not isinstance(service_def, dict):
            continue

        container_name = service_def.get("container_name")
        if container_name is None:
            # Derive from project name + service name (Docker Compose default)
            container_name = f"{project_name}-{service_name}-1"

        # Skip init containers (one-shot setup jobs)
        if container_name.endswith("-init"):
            continue

        # Use override or auto-generate display name
        display_name = _DISPLAY_NAME_OVERRIDES.get(
            container_name, _generate_display_name(container_name)
        )
        config[container_name] = {"display_name": display_name}

    logger.info("Discovered %d containers from compose.yml", len(config))
    return config, None


def _fetch_cadvisor_machine_info() -> dict[str, Any] | None:
    """Fetch machine info from cAdvisor with caching.

    Returns dict with num_cores, memory_capacity, etc.
    """
    global _machine_info_cache, _machine_info_cache_time

    now = time.time()
    if _machine_info_cache and (now - _machine_info_cache_time) < MACHINE_INFO_CACHE_TTL:
        return _machine_info_cache

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get("http://cadvisor:8080/api/v1.3/machine")
            if response.status_code == 200:
                _machine_info_cache = response.json()
                _machine_info_cache_time = now
                return _machine_info_cache
    except Exception as e:
        logger.debug(f"Failed to fetch cAdvisor machine info: {e}")

    return _machine_info_cache  # Return stale cache if fetch fails


def _fetch_cadvisor_stats() -> dict[str, Any] | None:
    """Fetch container stats from cAdvisor API.

    Returns dict mapping container name to stats, or None if unavailable.
    """
    cadvisor_url = "http://cadvisor:8080/api/v1.3/docker/"

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(cadvisor_url)
            if response.status_code == 200:
                return cast(dict[str, Any], response.json())
    except Exception as e:
        logger.debug(f"Failed to fetch cAdvisor stats: {e}")

    return None


def _calculate_cpu_percent(stats: list[dict[str, Any]]) -> float:
    """Calculate CPU percentage from cAdvisor stats.

    Uses the difference between the last two stats samples.
    Returns 0.0 if insufficient data.
    """
    if len(stats) < 2:
        return 0.0

    curr = stats[-1]
    prev = stats[-2]

    curr_cpu = curr.get("cpu", {}).get("usage", {}).get("total", 0)
    prev_cpu = prev.get("cpu", {}).get("usage", {}).get("total", 0)

    curr_time = curr.get("timestamp", "")
    prev_time = prev.get("timestamp", "")

    # Parse timestamps and calculate delta in nanoseconds
    from datetime import datetime as dt

    try:
        curr_dt = dt.fromisoformat(curr_time.replace("Z", "+00:00"))
        prev_dt = dt.fromisoformat(prev_time.replace("Z", "+00:00"))
        time_delta_ns = (curr_dt - prev_dt).total_seconds() * 1e9
    except Exception:
        return 0.0

    if time_delta_ns <= 0:
        return 0.0

    cpu_delta = curr_cpu - prev_cpu
    # cAdvisor reports CPU in nanoseconds, normalize to percentage
    cpu_percent = (cpu_delta / time_delta_ns) * 100

    return max(0.0, float(cpu_percent))  # No upper clamp - can exceed 100% for multi-core


def _parse_container_resource_metrics(
    container_name: str, data: dict[str, Any]
) -> tuple[float, float, float, float]:
    """Parse container resource metrics from cAdvisor data.

    Memory limit is extracted from cAdvisor's spec.memory.limit field,
    which reflects the actual Docker mem_limit setting from compose.yml.

    Returns: (memory_used_mb, memory_limit_mb, memory_percent, cpu_percent)
    """
    stats = data.get("stats", [])
    latest = stats[-1] if stats else {}

    # Memory metrics (working_set is the relevant metric for actual usage)
    memory = latest.get("memory", {})
    memory_working_set = memory.get("working_set", 0)
    memory_used_mb = memory_working_set / (1024 * 1024)

    # Get memory limit from cAdvisor spec (actual Docker container limit)
    spec = data.get("spec", {})
    memory_limit_bytes = spec.get("memory", {}).get("limit", 0)

    # Handle "unlimited" case: when no mem_limit is set in Docker,
    # cAdvisor reports max uint64 or a very large value
    MAX_REASONABLE_LIMIT = 64 * 1024 * 1024 * 1024  # 64 GB
    if memory_limit_bytes == 0 or memory_limit_bytes > MAX_REASONABLE_LIMIT:
        memory_limit_mb = 0.0
    else:
        memory_limit_mb = memory_limit_bytes / (1024 * 1024)

    # Calculate memory percentage
    memory_percent = (memory_used_mb / memory_limit_mb * 100) if memory_limit_mb > 0 else 0.0

    # CPU percentage
    cpu_percent = _calculate_cpu_percent(stats)

    return (
        round(memory_used_mb, 1),
        round(memory_limit_mb, 1),
        round(memory_percent, 1),
        round(cpu_percent, 1),
    )


def _find_container_in_cadvisor(
    container_name: str, cadvisor_data: dict[str, Any]
) -> dict[str, Any] | None:
    """Find a container's data in cAdvisor response by name."""
    for key, data in cadvisor_data.items():
        # Check if the container name is in the key or in the aliases
        if container_name in key:
            return cast(dict[str, Any], data)
        aliases = data.get("aliases", [])
        if container_name in aliases:
            return cast(dict[str, Any], data)
        # Check the name field
        if data.get("name", "").endswith(container_name):
            return cast(dict[str, Any], data)
    return None


@router.get("/infrastructure", response_model=InfrastructureResponse)
@limiter.limit("120/minute")
async def get_infrastructure_metrics(request: Request) -> InfrastructureResponse:
    """Returns unified infrastructure metrics for all services.

    Combines health check status with container resource metrics from cAdvisor.
    Each service includes:
    - Health status (healthy/degraded/unhealthy)
    - Health check latency
    - Memory usage and limit
    - CPU usage percentage
    """
    import asyncio

    from settings import get_settings

    settings = get_settings()

    def _determine_status(
        latency_ms: float | None,
        threshold_degraded: float = 100,
        threshold_unhealthy: float = 500,
    ) -> ContainerStatus:
        """Determine service status based on latency thresholds."""
        if latency_ms is None:
            return ContainerStatus.UNHEALTHY
        if latency_ms < threshold_degraded:
            return ContainerStatus.HEALTHY
        if latency_ms < threshold_unhealthy:
            return ContainerStatus.DEGRADED
        return ContainerStatus.UNHEALTHY

    async def check_redis() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Redis health via PING command."""
        redis_client = request.app.state.redis_client
        try:
            start = time.perf_counter()
            await redis_client.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            return _determine_status(latency_ms), round(latency_ms, 2), "Connected"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_osrm() -> tuple[ContainerStatus, float | None, str | None]:
        """Check OSRM health via test route request."""
        test_url = f"{settings.osrm.base_url}/route/v1/driving/-46.6388,-23.5475;-46.6355,-23.5505"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(test_url, params={"overview": "false"})
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        "Routing available",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_kafka() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Kafka health via metadata query."""
        from confluent_kafka.admin import AdminClient

        try:
            start = time.perf_counter()
            admin_config = {
                "bootstrap.servers": settings.kafka.bootstrap_servers,
                "socket.timeout.ms": 5000,
            }
            if settings.kafka.security_protocol != "PLAINTEXT":
                admin_config.update(
                    {
                        "security.protocol": settings.kafka.security_protocol,
                        "sasl.mechanisms": settings.kafka.sasl_mechanisms,
                        "sasl.username": settings.kafka.sasl_username,
                        "sasl.password": settings.kafka.sasl_password,
                    }
                )

            admin = AdminClient(admin_config)
            loop = asyncio.get_running_loop()
            metadata = await loop.run_in_executor(None, lambda: admin.list_topics(timeout=5.0))
            latency_ms = (time.perf_counter() - start) * 1000
            broker_count = len(metadata.brokers)
            return (
                _determine_status(latency_ms),
                round(latency_ms, 2),
                f"{broker_count} broker(s)",
            )
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    def check_simulation() -> tuple[ContainerStatus, float | None, str | None]:
        """Check simulation engine health."""
        engine = request.app.state.simulation_engine
        try:
            start = time.perf_counter()
            if engine is None:
                return ContainerStatus.UNHEALTHY, None, "Engine not initialized"
            state = engine.state.value
            _ = engine._env.now
            latency_ms = (time.perf_counter() - start) * 1000
            return ContainerStatus.HEALTHY, round(latency_ms, 2), f"State: {state}"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Error: {str(e)[:50]}"

    async def check_stream_processor() -> tuple[ContainerStatus, float | None, str | None]:
        """Check stream processor health via its HTTP API."""
        stream_processor_url = "http://stream-processor:8080/health"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(stream_processor_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unhealthy")
                    container_status = (
                        ContainerStatus(status)
                        if status in ["healthy", "degraded", "unhealthy"]
                        else ContainerStatus.UNHEALTHY
                    )
                    return container_status, round(latency_ms, 2), data.get("message")
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_schema_registry() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Schema Registry health via subjects endpoint."""
        schema_registry_url = "http://schema-registry:8081/subjects"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(schema_registry_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    subjects = response.json()
                    subject_count = len(subjects) if isinstance(subjects, list) else 0
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        (f"{subject_count} subjects" if subject_count > 0 else "Connected"),
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_minio() -> tuple[ContainerStatus, float | None, str | None]:
        """Check MinIO health via liveness endpoint."""
        minio_url = "http://minio:9000/minio/health/live"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(minio_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return _determine_status(latency_ms), round(latency_ms, 2), "Live"
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_spark_thrift() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Spark Thrift Server health via Spark UI API."""
        spark_url = "http://spark-thrift-server:4040/api/v1/applications"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(spark_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    apps = response.json()
                    app_count = len(apps) if isinstance(apps, list) else 0
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        f"{app_count} app(s)",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_localstack() -> tuple[ContainerStatus, float | None, str | None]:
        """Check LocalStack health via health endpoint."""
        localstack_url = "http://localstack:4566/_localstack/health"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(localstack_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", {})
                    running = sum(1 for s in services.values() if s == "running")
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        f"{running} services",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_prometheus() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Prometheus health via healthy endpoint."""
        prometheus_url = "http://prometheus:9090/-/healthy"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(prometheus_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        "Healthy",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_cadvisor() -> tuple[ContainerStatus, float | None, str | None]:
        """Check cAdvisor health via healthz endpoint."""
        cadvisor_url = "http://cadvisor:8080/healthz"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(cadvisor_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        "Healthy",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_grafana() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Grafana health via health endpoint."""
        grafana_url = "http://grafana:3000/api/health"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(grafana_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    data = response.json()
                    db_status = data.get("database", "unknown")
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        f"DB: {db_status}",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_airflow_web() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Airflow webserver health via health endpoint."""
        airflow_url = "http://airflow-webserver:8080/health"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(airflow_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    data = response.json()
                    metadb = data.get("metadatabase", {}).get("status", "unknown")
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        f"MetaDB: {metadb}",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    async def check_superset() -> tuple[ContainerStatus, float | None, str | None]:
        """Check Superset health via health endpoint."""
        superset_url = "http://superset:8088/health"
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(superset_url)
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    return (
                        _determine_status(latency_ms),
                        round(latency_ms, 2),
                        "Healthy",
                    )
                else:
                    return (
                        ContainerStatus.DEGRADED,
                        round(latency_ms, 2),
                        f"HTTP {response.status_code}",
                    )
        except httpx.TimeoutException:
            return ContainerStatus.UNHEALTHY, None, "Request timed out"
        except Exception as e:
            return ContainerStatus.UNHEALTHY, None, f"Connection failed: {str(e)[:50]}"

    # Run all health checks concurrently
    (
        redis_result,
        osrm_result,
        kafka_result,
        stream_processor_result,
        schema_registry_result,
        minio_result,
        spark_thrift_result,
        localstack_result,
        prometheus_result,
        cadvisor_result,
        grafana_result,
        airflow_web_result,
        superset_result,
    ) = await asyncio.gather(
        check_redis(),
        check_osrm(),
        check_kafka(),
        check_stream_processor(),
        check_schema_registry(),
        check_minio(),
        check_spark_thrift(),
        check_localstack(),
        check_prometheus(),
        check_cadvisor(),
        check_grafana(),
        check_airflow_web(),
        check_superset(),
    )
    simulation_result = check_simulation()

    # Default result for containers without health endpoints (status based on cAdvisor)
    no_health_endpoint = (ContainerStatus.HEALTHY, None, "No health endpoint")

    # Map container names to health check results
    health_results = {
        # Core profile
        "rideshare-kafka": kafka_result,
        "rideshare-schema-registry": schema_registry_result,
        "rideshare-redis": redis_result,
        "rideshare-osrm": osrm_result,
        "rideshare-simulation": simulation_result,
        "rideshare-stream-processor": stream_processor_result,
        "rideshare-frontend": no_health_endpoint,
        # Data Platform profile
        "rideshare-minio": minio_result,
        "rideshare-spark-thrift-server": spark_thrift_result,
        "rideshare-bronze-ingestion-high-volume": no_health_endpoint,
        "rideshare-bronze-ingestion-low-volume": no_health_endpoint,
        "rideshare-localstack": localstack_result,
        # Monitoring profile
        "rideshare-prometheus": prometheus_result,
        "rideshare-cadvisor": cadvisor_result,
        "rideshare-grafana": grafana_result,
        # Quality Orchestration profile
        "rideshare-postgres-airflow": no_health_endpoint,
        "rideshare-airflow-webserver": airflow_web_result,
        "rideshare-airflow-scheduler": no_health_endpoint,
        # BI profile
        "rideshare-postgres-superset": no_health_endpoint,
        "rideshare-redis-superset": no_health_endpoint,
        "rideshare-superset": superset_result,
        "rideshare-superset-celery-worker": no_health_endpoint,
    }

    # Fetch container resource metrics from cAdvisor
    cadvisor_data = _fetch_cadvisor_stats()
    cadvisor_available = cadvisor_data is not None

    # Fetch machine info for system-wide totals
    machine_info = _fetch_cadvisor_machine_info() if cadvisor_available else None
    total_cores = machine_info.get("num_cores", 1) if machine_info else 1
    # Memory capacity in bytes - convert to MB
    memory_capacity_bytes = machine_info.get("memory_capacity", 0) if machine_info else 0
    total_memory_capacity_mb = (
        memory_capacity_bytes / (1024 * 1024) if memory_capacity_bytes else 0.0
    )

    # Accumulators for system-wide totals
    total_cpu_raw = 0.0  # Sum of per-container CPU (raw, percentage of 1 core each)
    total_memory_used = 0.0

    # Build service metrics list
    container_config, discovery_error = _discover_containers()
    services = []
    for container_name, config in container_config.items():
        status, latency_ms, message = health_results.get(
            container_name, (ContainerStatus.HEALTHY, None, "No health endpoint")
        )

        # Get resource metrics from cAdvisor if available
        memory_used_mb = 0.0
        memory_limit_mb = 0.0
        memory_percent = 0.0
        cpu_percent = 0.0

        if cadvisor_available and cadvisor_data is not None:
            container_data = _find_container_in_cadvisor(container_name, cadvisor_data)
            if container_data:
                memory_used_mb, memory_limit_mb, memory_percent, cpu_percent_raw = (
                    _parse_container_resource_metrics(container_name, container_data)
                )
                # Accumulate totals (cpu_percent_raw is per-core, memory is in MB)
                total_cpu_raw += cpu_percent_raw
                total_memory_used += memory_used_mb
                # Normalize CPU for display (percentage of all cores)
                cpu_percent = round(cpu_percent_raw / total_cores, 1) if total_cores > 0 else 0.0
            else:
                # Container not found in cAdvisor - might be stopped
                if status == ContainerStatus.HEALTHY:
                    status = ContainerStatus.STOPPED
                    message = "Container not running"

        services.append(
            ServiceMetrics(
                name=str(config["display_name"]),
                status=status,
                latency_ms=latency_ms,
                message=message,
                memory_used_mb=memory_used_mb,
                memory_limit_mb=memory_limit_mb,
                memory_percent=memory_percent,
                cpu_percent=cpu_percent,
            )
        )

    # Determine overall status (exclude stream processor and frontend from overall calculation)
    core_statuses = [
        health_results["rideshare-kafka"][0],
        health_results["rideshare-redis"][0],
        health_results["rideshare-osrm"][0],
        health_results["rideshare-simulation"][0],
    ]

    if all(s == ContainerStatus.HEALTHY for s in core_statuses):
        overall_status = ContainerStatus.HEALTHY
    elif any(s == ContainerStatus.UNHEALTHY for s in core_statuses):
        overall_status = ContainerStatus.UNHEALTHY
    else:
        overall_status = ContainerStatus.DEGRADED

    # Calculate normalized totals
    # CPU: normalize by total cores (raw is percentage of 1 core)
    total_cpu_percent = (total_cpu_raw / total_cores) if total_cores > 0 else 0.0
    # Memory: calculate percentage of total capacity
    total_memory_percent = (
        (total_memory_used / total_memory_capacity_mb * 100)
        if total_memory_capacity_mb > 0
        else 0.0
    )

    return InfrastructureResponse(
        services=services,
        overall_status=overall_status,
        cadvisor_available=cadvisor_available,
        timestamp=time.time(),
        total_cpu_percent=round(total_cpu_percent, 1),
        total_memory_used_mb=round(total_memory_used, 1),
        total_memory_capacity_mb=round(total_memory_capacity_mb, 1),
        total_memory_percent=round(total_memory_percent, 1),
        total_cores=total_cores,
        discovery_error=discovery_error,
    )

    # NOTE: /metrics/prometheus endpoint removed.
    # Metrics are now exported via OTLP to the OTel Collector, which pushes
    # to Prometheus via remote_write. See services/otel-collector/ config.
