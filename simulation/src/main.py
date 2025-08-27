"""Simulation service entrypoint for Docker container."""

import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime

import simpy

from src.db.database import init_database
from src.engine import SimulationEngine
from src.geo.osrm_client import OSRMClient
from src.geo.zones import ZoneLoader
from src.kafka.producer import KafkaProducer
from src.matching.driver_geospatial_index import DriverGeospatialIndex
from src.matching.driver_registry import DriverRegistry
from src.matching.matching_server import MatchingServer
from src.matching.notification_dispatch import NotificationDispatch
from src.matching.surge_pricing import SurgePricingCalculator
from src.redis_client.publisher import RedisPublisher
from src.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class SimulationService:
    def __init__(self):
        self.settings = get_settings()
        self.engine: SimulationEngine | None = None
        self.running = False

    async def start(self):
        logger.info("Starting simulation service...")

        log_level = getattr(logging, self.settings.simulation.log_level)
        logging.getLogger().setLevel(log_level)

        env = simpy.Environment()
        session_factory = init_database("data/db/simulation.db")

        osrm = OSRMClient(self.settings.osrm.base_url)
        logger.info(f"OSRM client configured: {self.settings.osrm.base_url}")

        kafka = None
        try:
            kafka_config = {
                "bootstrap.servers": self.settings.kafka.bootstrap_servers,
                "security.protocol": self.settings.kafka.security_protocol,
            }
            if self.settings.kafka.security_protocol != "PLAINTEXT":
                kafka_config.update(
                    {
                        "sasl.mechanisms": self.settings.kafka.sasl_mechanisms,
                        "sasl.username": self.settings.kafka.sasl_username,
                        "sasl.password": self.settings.kafka.sasl_password,
                    }
                )
            kafka = KafkaProducer(kafka_config)
            logger.info("Kafka producer connected")
        except Exception as e:
            logger.warning(f"Kafka unavailable, running without event publishing: {e}")

        redis = None
        try:
            redis_config = {
                "host": self.settings.redis.host,
                "port": self.settings.redis.port,
                "db": 0,
                "password": self.settings.redis.password if self.settings.redis.password else None,
            }
            redis = RedisPublisher(redis_config)
            logger.info("Redis publisher configured")
        except Exception as e:
            logger.warning(f"Redis unavailable, running without visualization: {e}")

        zone_loader = ZoneLoader("data/sao-paulo/zones.geojson")
        driver_registry = DriverRegistry()
        driver_index = DriverGeospatialIndex()
        agent_registry: dict = {}
        notification_dispatch = NotificationDispatch(agent_registry)

        _ = SurgePricingCalculator(  # Starts its own SimPy process
            env=env,
            zone_loader=zone_loader,
            driver_registry=driver_registry,
            kafka_producer=kafka,
        )

        matching_server = MatchingServer(
            env=env,
            driver_index=driver_index,
            notification_dispatch=notification_dispatch,
            osrm_client=osrm,
            kafka_producer=kafka,
        )

        self.engine = SimulationEngine(
            matching_server=matching_server,
            kafka_producer=kafka,
            redis_client=redis,
            osrm_client=osrm,
            sqlite_db=session_factory,
            simulation_start_time=datetime.now(UTC),
        )

        self.running = True
        logger.info(
            f"Simulation engine initialized (speed: {self.settings.simulation.speed_multiplier}x)"
        )

        self.engine.start()

        while self.running:
            self.engine.step(10)
            await asyncio.sleep(0.1)

    async def stop(self):
        logger.info("Stopping simulation service...")
        self.running = False
        if self.engine:
            self.engine.stop()


async def main():
    service = SimulationService()

    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(service.stop())

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        await service.start()
    except KeyboardInterrupt:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
