"""
Rideshare Simulation Platform - Unified Entry Point

Runs the SimPy simulation engine alongside the FastAPI control panel API
in a single process. The simulation runs in a background thread while
FastAPI handles HTTP requests on the main thread.
"""

import logging
import signal
import sys
import threading
import time
from datetime import UTC, datetime

import simpy
import uvicorn
from redis.asyncio import Redis

from api.app import create_app
from db.database import init_database
from engine import SimulationEngine
from engine.agent_factory import AgentFactory
from geo.osrm_client import OSRMClient
from geo.zones import ZoneLoader
from kafka.producer import KafkaProducer
from matching.agent_registry_manager import AgentRegistryManager
from matching.driver_geospatial_index import DriverGeospatialIndex
from matching.driver_registry import DriverRegistry
from matching.matching_server import MatchingServer
from matching.notification_dispatch import NotificationDispatch
from matching.surge_pricing import SurgePricingCalculator
from redis_client.publisher import RedisPublisher
from settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SimulationRunner:
    """Manages the simulation loop in a background thread."""

    def __init__(self, engine: SimulationEngine):
        self._engine = engine
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        """Start the simulation loop in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Simulation loop started in background thread")

    def stop(self):
        """Stop the simulation loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Simulation loop stopped")

    def _run_loop(self):
        """Main simulation loop - advances simulation time."""
        while self._running:
            # Step simulation when running or draining (drain process needs env to advance)
            if self._engine.state.value in ("running", "draining"):
                self._engine.step(10)
            time.sleep(0.1)


def create_kafka_producer(settings) -> KafkaProducer | None:
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


def create_redis_publisher(settings) -> RedisPublisher | None:
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


def create_async_redis_client(settings) -> Redis:
    """Create async Redis client for FastAPI."""
    return Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password or None,
        decode_responses=True,
    )


def main():
    """Main entry point - initializes and runs the unified service."""
    settings = get_settings()

    log_level = getattr(logging, settings.simulation.log_level)
    logging.getLogger().setLevel(log_level)

    logger.info("Starting unified simulation service...")

    # Initialize SimPy environment and database
    env = simpy.Environment()
    session_factory = init_database("/app/db/simulation.db")

    # Initialize external service clients
    osrm_client = OSRMClient(settings.osrm.base_url)
    logger.info(f"OSRM client configured: {settings.osrm.base_url}")

    kafka_producer = create_kafka_producer(settings)
    if kafka_producer:
        logger.info("Kafka producer connected")

    redis_publisher = create_redis_publisher(settings)
    if redis_publisher:
        logger.info("Redis publisher configured")

    async_redis_client = create_async_redis_client(settings)
    logger.info("Async Redis client configured")

    # Load geographic data
    zone_loader = ZoneLoader("/app/data/sao-paulo/zones.geojson")

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
    )

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

    logger.info(f"Simulation engine initialized (speed: {settings.simulation.speed_multiplier}x)")

    # Create FastAPI app with real dependencies
    app = create_app(
        engine=engine,
        agent_factory=agent_factory,
        redis_client=async_redis_client,
    )

    # Add driver registry to app state for metrics
    app.state.driver_registry = driver_registry

    # Start simulation loop in background
    sim_runner = SimulationRunner(engine)
    sim_runner.start()

    # Handle shutdown signals
    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sim_runner.stop()
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
