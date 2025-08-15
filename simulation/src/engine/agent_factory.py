"""Factory for dynamic agent creation."""

from typing import TYPE_CHECKING
from uuid import uuid4

from agents.dna_generator import generate_driver_dna, generate_rider_dna
from agents.driver_agent import DriverAgent
from agents.rider_agent import RiderAgent

if TYPE_CHECKING:
    from engine import SimulationEngine
    from kafka.producer import KafkaProducer


class AgentFactory:
    """Factory for creating driver and rider agents dynamically."""

    def __init__(
        self,
        simulation_engine: "SimulationEngine",
        sqlite_db,
        kafka_producer: "KafkaProducer | None",
    ):
        self._simulation_engine = simulation_engine
        self._sqlite_db = sqlite_db
        self._kafka_producer = kafka_producer
        self._redis_publisher = getattr(simulation_engine, "_redis_client", None)

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
            )

            self._simulation_engine.register_driver(agent)

            if self._simulation_engine.state.value == "running":
                process = self._simulation_engine._env.process(agent.run())
                self._simulation_engine._agent_processes.append(process)

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
            )

            self._simulation_engine.register_rider(agent)

            if self._simulation_engine.state.value == "running":
                process = self._simulation_engine._env.process(agent.run())
                self._simulation_engine._agent_processes.append(process)

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
