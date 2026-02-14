"""
Rideshare Simulation Platform - Unified Entry Point

Runs the SimPy simulation engine alongside the FastAPI control panel API
in a single process. The simulation runs in a background thread while
FastAPI handles HTTP requests on the main thread.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime

import simpy
import uvicorn
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from redis.asyncio import Redis

from api.app import create_app
from db.database import init_database
from engine import SimulationEngine
from engine.agent_factory import AgentFactory
from geo.osrm_client import OSRMClient
from geo.zones import ZoneLoader
from kafka.producer import KafkaProducer
from kafka.serializer_registry import SerializerRegistry
from matching.agent_registry_manager import AgentRegistryManager
from matching.driver_geospatial_index import DriverGeospatialIndex
from matching.driver_registry import DriverRegistry
from matching.matching_server import MatchingServer
from matching.notification_dispatch import NotificationDispatch
from matching.surge_pricing import SurgePricingCalculator
from redis_client.publisher import RedisPublisher
from settings import Settings, get_settings

logger = logging.getLogger(__name__)


def init_otel_sdk() -> None:
    """Initialize OpenTelemetry SDK for metrics and traces.

    Configures TracerProvider and MeterProvider with OTLP gRPC exporters
    pointing to the OTel Collector. Must be called before creating the
    FastAPI app so auto-instrumentation can pick up the providers.
    """
    resource = Resource.create(
        {
            "service.name": "simulation",
            "service.version": "0.1.0",
            "deployment.environment": os.getenv("DEPLOYMENT_ENV", "local"),
        }
    )

    # Tracing
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(trace_provider)
    logger.info("OpenTelemetry tracing initialized (endpoint=%s)", otlp_endpoint)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    logger.info("OpenTelemetry metrics initialized")


class SimulationRunner:
    """Manages the simulation loop in a background thread."""

    def __init__(self, engine: SimulationEngine) -> None:
        self._engine = engine
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the simulation loop in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Simulation loop started in background thread")

    def stop(self) -> None:
        """Stop the simulation loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Simulation loop stopped")

    def _run_loop(self) -> None:
        """Main simulation loop - advances simulation time."""
        while self._running:
            # Step simulation when running or draining (drain process needs env to advance)
            if self._engine.state.value in ("running", "draining"):
                self._engine.step(10)
            time.sleep(0.1)


def create_kafka_producer(settings: Settings) -> KafkaProducer | None:
    """Create Kafka producer with settings."""
    try:
        kafka_config = {
            "bootstrap.servers": settings.kafka.bootstrap_servers,
            "security.protocol": settings.kafka.security_protocol,
        }
        if settings.kafka.security_protocol != "PLAINTEXT":
            kafka_config.update(
                {
                    "sasl.mechanisms": settings.kafka.sasl_mechanisms,
                    "sasl.username": settings.kafka.sasl_username,
                    "sasl.password": settings.kafka.sasl_password,
                }
            )
        return KafkaProducer(kafka_config)
    except Exception as e:
        logger.warning(f"Kafka unavailable, running without event publishing: {e}")
        return None


def create_redis_publisher(settings: Settings) -> RedisPublisher | None:
    """Create Redis publisher with settings."""
    try:
        redis_config = {
            "host": settings.redis.host,
            "port": settings.redis.port,
            "db": 0,
            "password": settings.redis.password if settings.redis.password else None,
        }
        return RedisPublisher(redis_config)
    except Exception as e:
        logger.warning(f"Redis publisher unavailable: {e}")
        return None


def create_async_redis_client(settings: Settings) -> "Redis[str]":
    """Create async Redis client for FastAPI."""
    return Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password or None,
        decode_responses=True,
    )


def main() -> None:
    """Main entry point - initializes and runs the unified service."""
    # Import logging setup from our logging module
    from sim_logging import setup_logging

    settings = get_settings()

    # Configure logging using centralized setup
    # LOG_FORMAT env var takes precedence, then settings.simulation.log_format
    log_format = os.environ.get("LOG_FORMAT") or settings.simulation.log_format
    setup_logging(
        level=settings.simulation.log_level,
        json_output=log_format == "json",
        environment=os.environ.get("ENVIRONMENT", "development"),
    )

    # Initialize OTel SDK before creating app (providers must exist for auto-instrumentation)
    init_otel_sdk()

    logger.info("Starting unified simulation service...")

    # Initialize SimPy environment and database
    db_path = os.environ.get("SIM_DB_PATH", "./db/simulation.db")
    env = simpy.Environment()
    session_factory = init_database(db_path)

    # Initialize external service clients
    osrm_client = OSRMClient(settings.osrm.base_url)
    logger.info(f"OSRM client configured: {settings.osrm.base_url}")

    kafka_producer = create_kafka_producer(settings)
    if kafka_producer:
        logger.info("Kafka producer connected")

    # Initialize Schema Registry integration if configured
    if settings.kafka.schema_registry_url and settings.kafka.schema_validation_enabled:
        try:
            from pathlib import Path

            # Schema path is relative to simulation/src, schemas are in project root
            schema_base_path = Path(__file__).parent.parent.parent / settings.kafka.schema_base_path
            SerializerRegistry.initialize(
                schema_registry_url=settings.kafka.schema_registry_url,
                schema_base_path=schema_base_path,
                basic_auth_user_info=settings.kafka.schema_registry_basic_auth_user_info,
            )
            logger.info(
                f"Schema Registry integration enabled: {settings.kafka.schema_registry_url}"
            )
        except Exception as e:
            logger.warning(f"Schema Registry unavailable, running without validation: {e}")

    redis_publisher = create_redis_publisher(settings)
    if redis_publisher:
        logger.info("Redis publisher configured")

    async_redis_client = create_async_redis_client(settings)
    logger.info("Async Redis client configured")

    # Load geographic data
    zones_path = os.environ.get("ZONES_PATH", "../data/zones.geojson")
    zone_loader = ZoneLoader(zones_path)

    # Initialize matching components
    driver_registry = DriverRegistry()
    driver_index = DriverGeospatialIndex()

    # Create matching server first (with placeholder notification_dispatch)
    matching_server = MatchingServer(
        env=env,
        driver_index=driver_index,
        notification_dispatch=None,  # Will be set after registry_manager is created
        osrm_client=osrm_client,
        kafka_producer=kafka_producer,
        registry_manager=None,  # Will be set after registry_manager is created
        redis_publisher=redis_publisher,  # For real-time trip updates
    )

    # Create AgentRegistryManager
    registry_manager = AgentRegistryManager(
        driver_index=driver_index,
        driver_registry=driver_registry,
        matching_server=matching_server,
    )

    # Create NotificationDispatch with registry_manager
    notification_dispatch = NotificationDispatch(registry_manager)

    # Wire notification_dispatch and registry_manager into matching_server
    matching_server._notification_dispatch = notification_dispatch
    matching_server._registry_manager = registry_manager

    # Initialize surge pricing calculator (starts its own SimPy process)
    surge_calculator = SurgePricingCalculator(
        env=env,
        zone_loader=zone_loader,
        driver_registry=driver_registry,
        kafka_producer=kafka_producer,
        redis_publisher=redis_publisher,
    )

    # Wire surge calculator into matching server
    matching_server._surge_calculator = surge_calculator

    # Initialize simulation engine with shared SimPy environment
    simulation_start_time = datetime.now(UTC)
    engine = SimulationEngine(
        env=env,
        matching_server=matching_server,
        kafka_producer=kafka_producer,
        redis_client=redis_publisher,
        osrm_client=osrm_client,
        sqlite_db=session_factory,
        simulation_start_time=simulation_start_time,
    )

    # Initialize agent factory with all dependencies
    agent_factory = AgentFactory(
        simulation_engine=engine,
        sqlite_db=session_factory,
        kafka_producer=kafka_producer,
        registry_manager=registry_manager,
        zone_loader=zone_loader,
        osrm_client=osrm_client,
        surge_calculator=surge_calculator,
    )

    # Set factory reference on engine for spawner processes
    engine._agent_factory = agent_factory

    # Restore from checkpoint if configured
    if settings.simulation.resume_from_checkpoint:
        restored = engine.try_restore_from_checkpoint()
        if restored:
            logger.info("Simulation restored from checkpoint")
        else:
            logger.info("No checkpoint found, starting fresh simulation")

    logger.info(f"Simulation engine initialized (speed: {settings.simulation.speed_multiplier}x)")

    # Create FastAPI app with real dependencies
    app = create_app(
        engine=engine,
        agent_factory=agent_factory,
        redis_client=async_redis_client,
        zone_loader=zone_loader,
        matching_server=matching_server,
    )

    # Add driver registry and surge calculator to app state for metrics and reset
    app.state.driver_registry = driver_registry
    app.state.surge_calculator = surge_calculator

    # Start simulation loop in background
    sim_runner = SimulationRunner(engine)
    sim_runner.start()

    # Handle shutdown signals
    def shutdown_handler(signum: int, frame: object) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        sim_runner.stop()

        if settings.simulation.checkpoint_enabled:
            try:
                engine.save_checkpoint()
                logger.info("Shutdown checkpoint saved")
            except Exception:
                logger.exception("Shutdown checkpoint failed")

        if engine.state.value == "running":
            engine.stop()
        if kafka_producer:
            kafka_producer.flush()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Run FastAPI server (blocking)
    logger.info("Starting unified simulation service on port 8000")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
