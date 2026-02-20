"""FastAPI application factory for simulation control panel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from slowapi.errors import RateLimitExceeded

if TYPE_CHECKING:
    from redis.asyncio import Redis

from api.auth import verify_api_key
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.models.health import (
    DetailedHealthResponse,
    ServiceHealth,
    StreamProcessorHealth,
)
from api.rate_limit import limiter, rate_limit_exceeded_handler
from api.redis_subscriber import RedisSubscriber
from api.routes import agents, metrics, puppet, simulation
from api.snapshots import StateSnapshotManager
from api.websocket import manager as connection_manager
from api.websocket import router as websocket_router
from settings import get_settings

if TYPE_CHECKING:
    from engine import SimulationEngine
    from engine.agent_factory import AgentFactory

logger = logging.getLogger(__name__)


class MetricsUpdater:
    """Periodically pushes simulation metrics to the OTel exporter."""

    def __init__(self, engine: SimulationEngine) -> None:
        self._engine = engine
        self._task: asyncio.Task[None] | None = None
        self._interval = 15.0  # seconds

    async def start(self) -> None:
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _update_loop(self) -> None:
        from metrics import get_metrics_collector
        from metrics.prometheus_exporter import update_metrics_from_snapshot

        while True:
            try:
                await asyncio.sleep(self._interval)
                collector = get_metrics_collector()
                snapshot = collector.get_snapshot()

                # Gather live counts from engine
                drivers_available = len(
                    [d for d in self._engine._active_drivers.values() if d.status == "available"]
                )
                riders_awaiting_pickup = len(
                    [
                        r
                        for r in self._engine._active_riders.values()
                        if r.status == "awaiting_pickup"
                    ]
                )
                riders_in_transit = len(
                    [r for r in self._engine._active_riders.values() if r.status == "on_trip"]
                )
                active_trips = 0
                pending_offers = 0
                trips_completed = 0
                trips_cancelled = 0
                if hasattr(self._engine, "_matching_server") and self._engine._matching_server:
                    ms = self._engine._matching_server
                    active_trips = (
                        len(ms.get_active_trips()) if hasattr(ms, "get_active_trips") else 0
                    )
                    trip_stats = ms.get_trip_stats()
                    trips_completed = trip_stats.get("completed_count", 0)
                    trips_cancelled = trip_stats.get("cancelled_count", 0)
                    pending_offers = (
                        len(ms._pending_offers) if hasattr(ms, "_pending_offers") else 0
                    )

                simpy_events = (
                    len(self._engine._env._queue) if hasattr(self._engine._env, "_queue") else 0
                )

                # Compute avg metrics from matching server stats
                avg_fare = 0.0
                avg_duration_minutes = 0.0
                avg_match_seconds = 0.0
                avg_pickup_seconds = 0.0
                matching_success_rate = 0.0
                if hasattr(self._engine, "_matching_server") and self._engine._matching_server:
                    ms = self._engine._matching_server
                    trip_stats = ms.get_trip_stats()
                    avg_fare = trip_stats.get("avg_fare", 0.0)
                    avg_duration_minutes = trip_stats.get("avg_duration_minutes", 0.0)
                    avg_match_seconds = trip_stats.get("avg_match_seconds", 0.0)
                    avg_pickup_seconds = trip_stats.get("avg_pickup_seconds", 0.0)

                    matching_stats = ms.get_matching_stats()
                    offers_sent = matching_stats.get("offers_sent", 0)
                    offers_accepted = matching_stats.get("offers_accepted", 0)
                    if offers_sent > 0:
                        matching_success_rate = (offers_accepted / offers_sent) * 100.0

                update_metrics_from_snapshot(
                    snapshot,
                    trips_completed=trips_completed,
                    trips_cancelled=trips_cancelled,
                    drivers_available=drivers_available,
                    riders_awaiting_pickup=riders_awaiting_pickup,
                    riders_in_transit=riders_in_transit,
                    active_trips=active_trips,
                    avg_fare=avg_fare,
                    avg_duration_minutes=avg_duration_minutes,
                    avg_match_seconds=avg_match_seconds,
                    avg_pickup_seconds=avg_pickup_seconds,
                    matching_success_rate=matching_success_rate,
                    pending_offers=pending_offers,
                    simpy_events=simpy_events,
                )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in metrics update loop")


class StatusBroadcaster:
    """Periodically broadcasts simulation status to WebSocket clients."""

    def __init__(
        self, engine: SimulationEngine, connection_manager: Any, snapshot_manager: Any
    ) -> None:
        self._engine = engine
        self._connection_manager = connection_manager
        self._snapshot_manager = snapshot_manager
        self._task: asyncio.Task[None] | None = None
        self._interval = 1.0  # seconds

    async def start(self) -> None:
        self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _broadcast_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                if self._connection_manager.active_connections:
                    snapshot = await self._snapshot_manager.get_snapshot(engine=self._engine)
                    await self._connection_manager.broadcast(
                        {
                            "type": "simulation_status",
                            "data": snapshot.get("simulation", {}),
                        }
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in status broadcast loop")


def create_app(
    engine: SimulationEngine,
    agent_factory: AgentFactory,
    redis_client: Redis[str],
    zone_loader: Any = None,
    matching_server: Any = None,
) -> FastAPI:
    """Create FastAPI application with injected dependencies.

    Args:
        engine: SimulationEngine instance
        agent_factory: AgentFactory for creating agents
        redis_client: Async Redis client for real-time updates
        zone_loader: ZoneLoader for geographic zone lookups (optional)
        matching_server: MatchingServer for trip matching (optional)
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        """Manage application startup and shutdown."""
        # Store event loop reference for thread-safe async calls from SimPy
        import asyncio

        engine.set_event_loop(asyncio.get_running_loop())

        snapshot_manager = StateSnapshotManager(redis_client)
        subscriber = RedisSubscriber(redis_client, connection_manager)
        broadcaster = StatusBroadcaster(engine, connection_manager, snapshot_manager)
        metrics_updater = MetricsUpdater(engine)

        app.state.snapshot_manager = snapshot_manager
        app.state.subscriber = subscriber
        app.state.broadcaster = broadcaster
        app.state.metrics_updater = metrics_updater

        await subscriber.start()
        await broadcaster.start()
        await metrics_updater.start()
        yield
        await metrics_updater.stop()
        await broadcaster.stop()
        await subscriber.stop()

    app = FastAPI(
        title="Rideshare Simulation Control Panel API",
        version="1.0.0",
        description="REST API for controlling simulation and streaming real-time updates",
        lifespan=lifespan,
    )

    # Auto-instrument FastAPI (generates traces for all HTTP requests)
    FastAPIInstrumentor.instrument_app(app)

    # Auto-instrument HTTPX (traces outbound HTTP calls, e.g. OSRM)
    HTTPXClientInstrumentor().instrument()

    # Add rate limiter state and exception handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Set core dependencies immediately (not in lifespan) so they're available for testing
    app.state.simulation_engine = engine
    app.state.engine = engine  # Keep for backward compatibility
    app.state.redis_client = redis_client
    app.state.agent_factory = agent_factory
    app.state.zone_loader = zone_loader
    app.state.matching_server = matching_server
    app.state.connection_manager = connection_manager

    settings = get_settings()
    origins = settings.cors.origins.split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(puppet.router, prefix="/agents", tags=["puppet"])
    app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
    app.include_router(websocket_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring (unauthenticated for infrastructure)."""
        return {"status": "healthy"}

    @app.get("/auth/validate")
    async def validate_api_key_endpoint(
        _: str = Depends(verify_api_key),
    ) -> dict[str, str]:
        """Validate API key for login.

        This endpoint requires a valid API key and returns 200 if valid.
        Used by the frontend login screen to validate credentials.
        Returns 401 if the API key is invalid.
        """
        return {"status": "authenticated"}

    def _determine_status(
        latency_ms: float | None,
        threshold_degraded: float = 100,
        threshold_unhealthy: float = 500,
    ) -> Literal["healthy", "degraded", "unhealthy"]:
        """Determine service status based on latency thresholds."""
        if latency_ms is None:
            return "unhealthy"
        if latency_ms < threshold_degraded:
            return "healthy"
        if latency_ms < threshold_unhealthy:
            return "degraded"
        return "unhealthy"

    @app.get("/health/detailed", response_model=DetailedHealthResponse)
    async def detailed_health_check() -> DetailedHealthResponse:
        """Detailed health check for all services with latency metrics."""

        async def check_redis() -> ServiceHealth:
            """Check Redis health via PING command."""
            redis_client = app.state.redis_client
            try:
                start = time.perf_counter()
                await redis_client.ping()
                latency_ms = (time.perf_counter() - start) * 1000
                return ServiceHealth(
                    status=_determine_status(latency_ms),
                    latency_ms=round(latency_ms, 2),
                    message="Connected",
                )
            except Exception as e:
                return ServiceHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message=f"Connection failed: {str(e)[:50]}",
                )

        async def check_osrm() -> ServiceHealth:
            """Check OSRM health via test route request."""
            settings = get_settings()
            # Use a simple route in Sao Paulo for health check
            test_url = (
                f"{settings.osrm.base_url}/route/v1/driving/-46.6388,-23.5475;-46.6355,-23.5505"
            )

            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(test_url, params={"overview": "false"})
                    latency_ms = (time.perf_counter() - start) * 1000

                    if response.status_code == 200:
                        return ServiceHealth(
                            status=_determine_status(latency_ms),
                            latency_ms=round(latency_ms, 2),
                            message="Routing available",
                        )
                    else:
                        return ServiceHealth(
                            status="degraded",
                            latency_ms=round(latency_ms, 2),
                            message=f"HTTP {response.status_code}",
                        )
            except httpx.TimeoutException:
                return ServiceHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message="Request timed out",
                )
            except Exception as e:
                return ServiceHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message=f"Connection failed: {str(e)[:50]}",
                )

        async def check_kafka() -> ServiceHealth:
            """Check Kafka health via metadata query."""
            from confluent_kafka.admin import AdminClient

            settings = get_settings()

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
                # list_topics() is blocking, run in executor
                loop = asyncio.get_running_loop()
                metadata = await loop.run_in_executor(None, lambda: admin.list_topics(timeout=5.0))
                latency_ms = (time.perf_counter() - start) * 1000

                broker_count = len(metadata.brokers)
                return ServiceHealth(
                    status=_determine_status(latency_ms),
                    latency_ms=round(latency_ms, 2),
                    message=f"{broker_count} broker(s) available",
                )
            except Exception as e:
                return ServiceHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message=f"Connection failed: {str(e)[:50]}",
                )

        def check_simulation_engine() -> ServiceHealth:
            """Check simulation engine health."""
            engine = app.state.simulation_engine

            try:
                start = time.perf_counter()
                # Check if engine exists and has valid state
                if engine is None:
                    return ServiceHealth(
                        status="unhealthy",
                        latency_ms=None,
                        message="Engine not initialized",
                    )

                state = engine.state.value
                # Check if SimPy environment is valid
                _ = engine._env.now
                latency_ms = (time.perf_counter() - start) * 1000

                return ServiceHealth(
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                    message=f"State: {state}",
                )
            except Exception as e:
                return ServiceHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message=f"Error: {str(e)[:50]}",
                )

        async def check_stream_processor() -> StreamProcessorHealth:
            """Check stream processor health via its HTTP API."""
            # Use internal Docker network URL
            stream_processor_url = "http://stream-processor:8080/health"

            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(stream_processor_url)
                    latency_ms = (time.perf_counter() - start) * 1000

                    if response.status_code == 200:
                        data = response.json()
                        return StreamProcessorHealth(
                            status=data.get("status", "unhealthy"),
                            latency_ms=round(latency_ms, 2),
                            message=data.get("message"),
                            kafka_connected=data.get("kafka_connected"),
                            redis_connected=data.get("redis_connected"),
                        )
                    else:
                        return StreamProcessorHealth(
                            status="degraded",
                            latency_ms=round(latency_ms, 2),
                            message=f"HTTP {response.status_code}",
                        )
            except httpx.TimeoutException:
                return StreamProcessorHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message="Request timed out",
                )
            except Exception as e:
                return StreamProcessorHealth(
                    status="unhealthy",
                    latency_ms=None,
                    message=f"Connection failed: {str(e)[:50]}",
                )

        # Run all checks concurrently
        redis_health, osrm_health, kafka_health, stream_processor_health = await asyncio.gather(
            check_redis(),
            check_osrm(),
            check_kafka(),
            check_stream_processor(),
        )
        engine_health = check_simulation_engine()

        # Determine overall status (stream_processor is optional, don't affect overall)
        core_statuses = [
            redis_health.status,
            osrm_health.status,
            kafka_health.status,
            engine_health.status,
        ]

        overall: Literal["healthy", "degraded", "unhealthy"]
        if all(s == "healthy" for s in core_statuses):
            overall = "healthy"
        elif any(s == "unhealthy" for s in core_statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"

        return DetailedHealthResponse(
            overall_status=overall,
            redis=redis_health,
            osrm=osrm_health,
            kafka=kafka_health,
            simulation_engine=engine_health,
            stream_processor=stream_processor_health,
            timestamp=datetime.now(UTC).isoformat(),
        )

    return app
