import logging
import time
from collections.abc import Callable
from typing import Annotated, Any, cast

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
from metrics import get_metrics_collector
from trip import TripState

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

CACHE_TTL = 0.5  # 500ms for responsive updates
_metrics_cache: dict = {}


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


def _get_cached_or_compute(cache_key: str, compute_func: Callable):
    now = time.time()
    if cache_key in _metrics_cache:
        entry = _metrics_cache[cache_key]
        if entry["expires_at"] > now:
            return entry["data"]

    data = compute_func()
    _metrics_cache[cache_key] = {"data": data, "expires_at": now + CACHE_TTL}
    return data


@router.get("/overview", response_model=OverviewMetrics)
def get_overview_metrics(engine: EngineDep, driver_registry: DriverRegistryDep):
    """Returns overview metrics with total counts."""

    def compute():
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
def get_zone_metrics(engine: EngineDep, driver_registry: DriverRegistryDep):
    """Returns per-zone metrics with supply, demand, and surge."""

    def compute():
        zones = []
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
def get_trip_metrics(engine: EngineDep):
    """Returns trip statistics including active, completed, and averages."""

    def compute():
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
def get_driver_metrics(driver_registry: DriverRegistryDep):
    """Returns driver status counts."""

    def compute():
        if not driver_registry:
            return DriverMetrics(
                online=0,
                offline=0,
                busy=0,
                en_route_pickup=0,
                en_route_destination=0,
                total=0,
            )

        status_counts = driver_registry.get_all_status_counts()
        online = status_counts.get("online", 0)
        offline = status_counts.get("offline", 0)
        busy = status_counts.get("busy", 0)
        en_route_pickup = status_counts.get("en_route_pickup", 0)
        en_route_destination = status_counts.get("en_route_destination", 0)
        total = online + offline + busy + en_route_pickup + en_route_destination

        return DriverMetrics(
            online=online,
            offline=offline,
            busy=busy,
            en_route_pickup=en_route_pickup,
            en_route_destination=en_route_destination,
            total=total,
        )

    return _get_cached_or_compute("drivers", compute)


@router.get("/riders", response_model=RiderMetrics)
def get_rider_metrics(engine: EngineDep, matching_server: MatchingServerDep):
    """Returns rider status counts derived from trip states.

    Rider states:
    - offline: No active trip
    - matched: Trip state in (REQUESTED, OFFER_SENT, MATCHED)
    - to_pickup: Trip state in (DRIVER_EN_ROUTE, DRIVER_ARRIVED)
    - in_transit: Trip state is STARTED
    """

    def compute():
        if not hasattr(engine, "_active_riders"):
            return RiderMetrics(offline=0, matched=0, to_pickup=0, in_transit=0, total=0)

        # Build rider -> trip state map from active trips
        rider_trip_states: dict[str, TripState] = {}
        if matching_server and hasattr(matching_server, "get_active_trips"):
            for trip in matching_server.get_active_trips():
                rider_trip_states[trip.rider_id] = trip.state

        offline = matched = to_pickup = in_transit = 0

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
                # Trip is in matching phase
                matched += 1
            elif trip_state in (TripState.DRIVER_EN_ROUTE, TripState.DRIVER_ARRIVED):
                # Driver is heading to pickup or waiting
                to_pickup += 1
            elif trip_state == TripState.STARTED:
                # Rider is in vehicle
                in_transit += 1
            else:
                # COMPLETED or CANCELLED shouldn't be in active trips
                offline += 1

        total = offline + matched + to_pickup + in_transit
        return RiderMetrics(
            offline=offline,
            matched=matched,
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
def get_performance_metrics(engine: EngineDep):
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
            stats = snapshot.errors[component]
            error_model = ErrorStats(
                count=stats.count,
                per_second=stats.per_second,
                by_type=stats.by_type,
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


# Container configuration for infrastructure monitoring
CONTAINER_CONFIG = {
    "rideshare-kafka": {
        "display_name": "Kafka",
        "memory_limit_bytes": 1 * 1024 * 1024 * 1024,  # 1 GB
    },
    "rideshare-redis": {
        "display_name": "Redis",
        "memory_limit_bytes": 512 * 1024 * 1024,  # 512 MB
    },
    "rideshare-osrm": {
        "display_name": "OSRM",
        "memory_limit_bytes": 3 * 1024 * 1024 * 1024,  # 3 GB
    },
    "rideshare-simulation": {
        "display_name": "Simulation",
        "memory_limit_bytes": 4 * 1024 * 1024 * 1024,  # 4 GB
    },
    "rideshare-stream-processor": {
        "display_name": "Stream Processor",
        "memory_limit_bytes": 512 * 1024 * 1024,  # 512 MB
    },
    "rideshare-frontend": {
        "display_name": "Frontend",
        "memory_limit_bytes": 512 * 1024 * 1024,  # 512 MB
    },
}


def _fetch_cadvisor_stats() -> dict | None:
    """Fetch container stats from cAdvisor API.

    Returns dict mapping container name to stats, or None if unavailable.
    """
    cadvisor_url = "http://cadvisor:8080/api/v1.3/docker/"

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(cadvisor_url)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.debug(f"Failed to fetch cAdvisor stats: {e}")

    return None


def _calculate_cpu_percent(stats: list[dict]) -> float:
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
    from datetime import datetime

    try:
        curr_dt = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))
        prev_dt = datetime.fromisoformat(prev_time.replace("Z", "+00:00"))
        time_delta_ns = (curr_dt - prev_dt).total_seconds() * 1e9
    except Exception:
        return 0.0

    if time_delta_ns <= 0:
        return 0.0

    cpu_delta = curr_cpu - prev_cpu
    # cAdvisor reports CPU in nanoseconds, normalize to percentage
    cpu_percent = (cpu_delta / time_delta_ns) * 100

    return max(0.0, min(cpu_percent, 100.0))


def _parse_container_resource_metrics(
    container_name: str, data: dict, config: dict
) -> tuple[float, float, float, float]:
    """Parse container resource metrics from cAdvisor data.

    Returns: (memory_used_mb, memory_limit_mb, memory_percent, cpu_percent)
    """
    stats = data.get("stats", [])
    latest = stats[-1] if stats else {}

    # Memory metrics (working_set is the relevant metric for actual usage)
    memory = latest.get("memory", {})
    memory_working_set = memory.get("working_set", 0)
    memory_used_mb = memory_working_set / (1024 * 1024)

    # Get memory limit from config
    memory_limit_bytes = config.get("memory_limit_bytes", 0)
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


def _find_container_in_cadvisor(container_name: str, cadvisor_data: dict) -> dict | None:
    """Find a container's data in cAdvisor response by name."""
    for key, data in cadvisor_data.items():
        # Check if the container name is in the key or in the aliases
        if container_name in key:
            return data
        aliases = data.get("aliases", [])
        if container_name in aliases:
            return data
        # Check the name field
        if data.get("name", "").endswith(container_name):
            return data
    return None


@router.get("/infrastructure", response_model=InfrastructureResponse)
async def get_infrastructure_metrics(request: Request):
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
                    return _determine_status(latency_ms), round(latency_ms, 2), "Routing available"
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
            return _determine_status(latency_ms), round(latency_ms, 2), f"{broker_count} broker(s)"
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

    # Run all health checks concurrently
    redis_result, osrm_result, kafka_result, stream_processor_result = await asyncio.gather(
        check_redis(),
        check_osrm(),
        check_kafka(),
        check_stream_processor(),
    )
    simulation_result = check_simulation()

    # Map container names to health check results
    health_results = {
        "rideshare-kafka": kafka_result,
        "rideshare-redis": redis_result,
        "rideshare-osrm": osrm_result,
        "rideshare-simulation": simulation_result,
        "rideshare-stream-processor": stream_processor_result,
        "rideshare-frontend": (
            ContainerStatus.HEALTHY,
            None,
            "No health endpoint",
        ),  # Frontend has no health check
    }

    # Fetch container resource metrics from cAdvisor
    cadvisor_data = _fetch_cadvisor_stats()
    cadvisor_available = cadvisor_data is not None

    # Build service metrics list
    services = []
    for container_name, config in CONTAINER_CONFIG.items():
        status, latency_ms, message = health_results.get(
            container_name, (ContainerStatus.STOPPED, None, "Unknown")
        )

        # Get resource metrics from cAdvisor if available
        memory_used_mb = 0.0
        memory_limit_bytes = cast(int, config.get("memory_limit_bytes", 0))
        memory_limit_mb = float(memory_limit_bytes) / (1024 * 1024) if memory_limit_bytes else 0.0
        memory_percent = 0.0
        cpu_percent = 0.0

        if cadvisor_available and cadvisor_data is not None:
            container_data = _find_container_in_cadvisor(container_name, cadvisor_data)
            if container_data:
                memory_used_mb, memory_limit_mb, memory_percent, cpu_percent = (
                    _parse_container_resource_metrics(container_name, container_data, config)
                )
            else:
                # Container not found in cAdvisor - might be stopped
                if status == ContainerStatus.HEALTHY:
                    status = ContainerStatus.STOPPED
                    message = "Container not running"

        services.append(
            ServiceMetrics(
                name=config["display_name"],
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

    return InfrastructureResponse(
        services=services,
        overall_status=overall_status,
        cadvisor_available=cadvisor_available,
        timestamp=time.time(),
    )
