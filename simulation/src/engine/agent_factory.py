"""Factory for dynamic agent creation."""

from typing import TYPE_CHECKING
from uuid import uuid4

from agents.dna_generator import generate_driver_dna, generate_rider_dna
from agents.driver_agent import DriverAgent
from agents.rider_agent import RiderAgent

if TYPE_CHECKING:
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient
    from geo.zones import ZoneLoader
    from kafka.producer import KafkaProducer
    from matching.agent_registry_manager import AgentRegistryManager
    from matching.surge_pricing import SurgePricingCalculator


class AgentFactory:
    """Factory for creating driver and rider agents dynamically."""

    def __init__(
        self,
        simulation_engine: "SimulationEngine",
        sqlite_db,
        kafka_producer: "KafkaProducer | None",
        registry_manager: "AgentRegistryManager | None" = None,
        zone_loader: "ZoneLoader | None" = None,
        osrm_client: "OSRMClient | None" = None,
        surge_calculator: "SurgePricingCalculator | None" = None,
    ):
        self._simulation_engine = simulation_engine
        self._sqlite_db = sqlite_db
        self._kafka_producer = kafka_producer
        self._redis_publisher = getattr(simulation_engine, "_redis_client", None)
        self._registry_manager = registry_manager
        self._zone_loader = zone_loader
        self._osrm_client = osrm_client
        self._surge_calculator = surge_calculator

        self._max_drivers = 2000
        self._max_riders = 10000

    def create_drivers(self, count: int) -> list[str]:
        """Create N driver agents."""
        self._check_driver_capacity(count)

        created_ids = []
        for _ in range(count):
            dna = generate_driver_dna()
            driver_id = str(uuid4())

            agent = DriverAgent(
                driver_id=driver_id,
                dna=dna,
                env=self._simulation_engine._env,
                kafka_producer=self._kafka_producer,
                redis_publisher=self._redis_publisher,
                driver_repository=None,
                registry_manager=self._registry_manager,
                zone_loader=self._zone_loader,
                immediate_online=True,  # Go online immediately when created dynamically
            )

            self._simulation_engine.register_driver(agent)

            # Register in AgentRegistryManager
            if self._registry_manager:
                self._registry_manager.register_driver(agent)

            # Agent is registered but process not started yet
            # Engine will pick up pending agents on next step cycle (thread-safe)

            created_ids.append(driver_id)

        return created_ids

    def create_riders(self, count: int) -> list[str]:
        """Create N rider agents."""
        self._check_rider_capacity(count)

        created_ids = []
        for _ in range(count):
            dna = generate_rider_dna()
            rider_id = str(uuid4())

            agent = RiderAgent(
                rider_id=rider_id,
                dna=dna,
                env=self._simulation_engine._env,
                kafka_producer=self._kafka_producer,
                redis_publisher=self._redis_publisher,
                rider_repository=None,
                simulation_engine=self._simulation_engine,
                zone_loader=self._zone_loader,
                osrm_client=self._osrm_client,
                surge_calculator=self._surge_calculator,
                immediate_first_trip=True,  # Request trip immediately
            )

            self._simulation_engine.register_rider(agent)

            # Register in AgentRegistryManager
            if self._registry_manager:
                self._registry_manager.register_rider(agent)

            # Agent is registered but process not started yet
            # Engine will pick up pending agents on next step cycle (thread-safe)

            created_ids.append(rider_id)

        return created_ids

    def _check_driver_capacity(self, count: int) -> None:
        """Verify adding count drivers won't exceed limit."""
        current_count = len(self._simulation_engine._active_drivers)
        if current_count + count > self._max_drivers:
            raise ValueError(
                f"Driver capacity limit exceeded: {current_count} + {count} > {self._max_drivers}"
            )

    def _check_rider_capacity(self, count: int) -> None:
        """Verify adding count riders won't exceed limit."""
        current_count = len(self._simulation_engine._active_riders)
        if current_count + count > self._max_riders:
            raise ValueError(
                f"Rider capacity limit exceeded: {current_count} + {count} > {self._max_riders}"
            )
