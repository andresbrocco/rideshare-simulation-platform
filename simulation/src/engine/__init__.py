"""SimPy environment orchestrator for rideshare simulation."""

from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import simpy

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from geo.osrm_client import OSRMClient
    from kafka.producer import KafkaProducer
    from matching.matching_server import MatchingServer
    from redis_client.publisher import RedisPublisher
    from trip import Trip


class SimulationState(str, Enum):
    """Simulation states."""

    STOPPED = "stopped"
    RUNNING = "running"
    DRAINING = "draining"
    PAUSED = "paused"


VALID_STATE_TRANSITIONS = {
    SimulationState.STOPPED: {SimulationState.RUNNING},
    SimulationState.RUNNING: {SimulationState.DRAINING, SimulationState.STOPPED},
    SimulationState.DRAINING: {SimulationState.PAUSED},
    SimulationState.PAUSED: {SimulationState.RUNNING},
}


class TimeManager:
    """Manages simulation time conversions."""

    def __init__(self, simulation_start_time: datetime, env: simpy.Environment):
        self._simulation_start_time = simulation_start_time.astimezone(UTC)
        self._env = env

    def current_time(self) -> datetime:
        """Convert SimPy now to datetime."""
        elapsed_seconds = int(self._env.now)
        return self._simulation_start_time + timedelta(seconds=elapsed_seconds)

    def format_timestamp(self, dt: datetime | None = None) -> str:
        """Format datetime as ISO 8601 UTC string."""
        if dt is None:
            dt = self.current_time()
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_datetime(self, simulated_seconds: float) -> datetime:
        """Convert SimPy seconds to datetime."""
        return self._simulation_start_time + timedelta(seconds=simulated_seconds)

    def to_seconds(self, dt: datetime) -> float:
        """Convert datetime to SimPy seconds since start."""
        delta = dt.astimezone(UTC) - self._simulation_start_time
        return delta.total_seconds()

    def elapsed_time(self) -> timedelta:
        """Returns elapsed simulation time."""
        return timedelta(seconds=self._env.now)

    def current_day(self) -> int:
        """Returns 0-indexed day number."""
        return int(self._env.now // 86400)

    def time_of_day(self) -> int:
        """Returns seconds since midnight (0-86399)."""
        return int(self._env.now % 86400)

    def is_business_hours(self) -> bool:
        """Returns True if current time is 9 AM - 6 PM, Monday-Friday."""
        current = self.current_time()
        weekday = current.weekday()
        hour = current.hour
        return 0 <= weekday <= 4 and 9 <= hour < 18

    def format_duration(self, seconds: float) -> str:
        """Format seconds as human-readable duration."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


class SimulationEngine:
    """Orchestrates SimPy environment, agents, and periodic processes."""

    def __init__(
        self,
        matching_server: "MatchingServer",
        kafka_producer: "KafkaProducer | None",
        redis_client: "RedisPublisher | None",
        osrm_client: "OSRMClient",
        sqlite_db: Any,
        simulation_start_time: datetime,
    ):
        self._env = simpy.Environment()
        self._state = SimulationState.STOPPED
        self._matching_server = matching_server
        self._kafka_producer = kafka_producer
        self._redis_client = redis_client
        self._osrm_client = osrm_client
        self._sqlite_db = sqlite_db

        self._active_drivers: dict[str, DriverAgent] = {}
        self._active_riders: dict[str, RiderAgent] = {}
        self._agent_processes: list[simpy.Process] = []
        self._periodic_processes: list[simpy.Process] = []

        self._time_manager = TimeManager(simulation_start_time, self._env)

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def active_driver_count(self) -> int:
        """Count drivers with status=online."""
        return sum(1 for driver in self._active_drivers.values() if driver.status == "online")

    @property
    def active_rider_count(self) -> int:
        """Count riders with status=waiting or in_trip."""
        return sum(
            1 for rider in self._active_riders.values() if rider.status in ("waiting", "in_trip")
        )

    def transition_state(self, new_state: SimulationState) -> None:
        """Validate and execute state transition."""
        if new_state not in VALID_STATE_TRANSITIONS.get(self._state, set()):
            raise ValueError(
                f"Invalid state transition from {self._state.value} to {new_state.value}"
            )

        old_state = self._state
        self._state = new_state
        self._emit_control_event(f"simulation.{new_state.value}", old_state)

    def register_driver(self, driver: "DriverAgent") -> None:
        """Add driver to active registry."""
        self._active_drivers[driver.driver_id] = driver

    def register_rider(self, rider: "RiderAgent") -> None:
        """Add rider to active registry."""
        self._active_riders[rider.rider_id] = rider

    def start(self) -> None:
        """Transition to RUNNING and launch all processes."""
        old_state = self._state
        self._state = SimulationState.RUNNING
        self._emit_control_event("simulation.started", old_state)
        self._start_agent_processes()
        self._start_periodic_processes()

    def stop(self) -> None:
        """Transition to STOPPED and halt all processes."""
        self.transition_state(SimulationState.STOPPED)

    def step(self, seconds: int) -> None:
        """Advance simulation by specified seconds."""
        target_time = self._env.now + seconds
        self._env.run(until=target_time)

    def resume(self) -> None:
        """Transition from PAUSED to RUNNING."""
        self.transition_state(SimulationState.RUNNING)
        self._start_agent_processes()
        self._start_periodic_processes()

    def current_time(self) -> datetime:
        """Get current simulated time as datetime."""
        return self._time_manager.current_time()

    async def request_match(
        self,
        rider_id: str,
        pickup_location: tuple[float, float],
        dropoff_location: tuple[float, float],
        pickup_zone_id: str,
        dropoff_zone_id: str,
        surge_multiplier: float,
        fare: float,
    ) -> "Trip | None":
        """Delegate to matching server."""
        return await self._matching_server.request_match(
            rider_id=rider_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )

    def _start_agent_processes(self) -> None:
        """Launch all registered agent run() processes."""
        for driver in self._active_drivers.values():
            process = self._env.process(driver.run())
            self._agent_processes.append(process)

        for rider in self._active_riders.values():
            process = self._env.process(rider.run())
            self._agent_processes.append(process)

    def _start_periodic_processes(self) -> None:
        """Start surge updates and GPS pings."""
        surge_process = self._env.process(self._surge_update_process())
        self._periodic_processes.append(surge_process)

        gps_process = self._env.process(self._gps_ping_process())
        self._periodic_processes.append(gps_process)

    def _surge_update_process(self):
        """Recalculate surge every 60 simulated seconds."""
        while True:
            if hasattr(self._matching_server, "update_surge_pricing"):
                self._matching_server.update_surge_pricing()

            if self._kafka_producer:
                event = {
                    "event_id": str(uuid4()),
                    "event_type": "surge.updated",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                self._kafka_producer.produce(
                    topic="surge-updates",
                    key="global",
                    value=event,
                )

            yield self._env.timeout(60)

    def _gps_ping_process(self):
        """Emit GPS pings for online drivers every 5 seconds."""
        while True:
            yield self._env.timeout(5)

            for driver in self._active_drivers.values():
                if driver.status == "online" and driver.location and self._kafka_producer:
                    event = {
                        "event_id": str(uuid4()),
                        "entity_type": "driver",
                        "entity_id": driver.driver_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "location": list(driver.location),
                        "trip_id": driver.active_trip,
                    }
                    self._kafka_producer.produce(
                        topic="gps-pings",
                        key=driver.driver_id,
                        value=event,
                    )

    def _emit_control_event(self, event_type: str, old_state: SimulationState) -> None:
        """Emit simulation control event."""
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_state": old_state.value,
            "new_state": self._state.value,
        }

        self._kafka_producer.produce(
            topic="simulation-control",
            key="engine",
            value=event,
        )
