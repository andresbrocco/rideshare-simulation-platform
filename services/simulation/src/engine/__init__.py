"""SimPy environment orchestrator for rideshare simulation."""

import asyncio
import logging
import time
import weakref
from collections import deque
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

from core.correlation import setup_correlation_logging
from engine.agent_factory import AgentFactory
from engine.snapshots import AgentSnapshot, SimulationSnapshot, TripSnapshot
from engine.thread_coordinator import (
    Command,
    CommandTimeoutError,
    CommandType,
    NoHandlerRegisteredError,
    ShutdownError,
    ThreadCoordinator,
)
from settings import get_settings

__all__ = [
    "SimulationEngine",
    "SimulationState",
    "TimeManager",
    "AgentFactory",
    # Thread coordination
    "ThreadCoordinator",
    "CommandType",
    "Command",
    "CommandTimeoutError",
    "NoHandlerRegisteredError",
    "ShutdownError",
    # Snapshots
    "AgentSnapshot",
    "TripSnapshot",
    "SimulationSnapshot",
]

logger = logging.getLogger(__name__)


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
        env: simpy.Environment,
        matching_server: "MatchingServer",
        kafka_producer: "KafkaProducer | None",
        redis_client: "RedisPublisher | None",
        osrm_client: "OSRMClient",
        sqlite_db: Any,
        simulation_start_time: datetime,
    ):
        self._env = env
        self._state = SimulationState.STOPPED
        self._matching_server = matching_server
        self._kafka_producer = kafka_producer
        self._redis_client = redis_client
        self._osrm_client = osrm_client
        self._sqlite_db = sqlite_db

        self._active_drivers: dict[str, DriverAgent] = {}
        self._active_riders: dict[str, RiderAgent] = {}
        self._pending_agents: deque[DriverAgent | RiderAgent] = deque()
        self._agent_processes: weakref.WeakSet[simpy.Process] = weakref.WeakSet()
        self._periodic_processes: list[simpy.Process] = []
        self._active_driver_counter: int = 0
        self._active_rider_counter: int = 0

        self._time_manager = TimeManager(simulation_start_time, self._env)
        self._speed_multiplier = 1
        self._drain_process: simpy.Process | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

        # Unique session ID for this simulation run (for distributed tracing)
        self._session_id = str(uuid4())
        setup_correlation_logging(self._session_id)

        # Agent factory reference (set later by main.py)
        self._agent_factory: AgentFactory | None = None

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def session_id(self) -> str:
        """Unique identifier for this simulation run (for distributed tracing)."""
        return self._session_id

    @property
    def time_manager(self) -> TimeManager:
        return self._time_manager

    @property
    def speed_multiplier(self) -> int:
        return self._speed_multiplier

    @property
    def active_driver_count(self) -> int:
        """Count of registered drivers (O(1) via incremental counter)."""
        return self._active_driver_counter

    @property
    def active_rider_count(self) -> int:
        """Count of registered riders (O(1) via incremental counter)."""
        return self._active_rider_counter

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to the main asyncio event loop for thread-safe async calls."""
        self._event_loop = loop

    def get_event_loop(self) -> asyncio.AbstractEventLoop | None:
        """Get the main asyncio event loop for thread-safe async calls from SimPy thread."""
        return self._event_loop

    def transition_state(self, new_state: SimulationState, trigger: str = "user_request") -> None:
        """Validate and execute state transition."""
        if new_state not in VALID_STATE_TRANSITIONS.get(self._state, set()):
            raise ValueError(
                f"Invalid state transition from {self._state.value} to {new_state.value}"
            )

        old_state = self._state
        self._state = new_state
        self._emit_control_event(f"simulation.{new_state.value}", old_state, trigger)

    def register_driver(self, driver: "DriverAgent") -> None:
        """Add driver to active registry and pending queue."""
        self._active_drivers[driver.driver_id] = driver
        self._active_driver_counter += 1
        self._pending_agents.append(driver)

    def register_rider(self, rider: "RiderAgent") -> None:
        """Add rider to active registry and pending queue."""
        self._active_riders[rider.rider_id] = rider
        self._active_rider_counter += 1
        self._pending_agents.append(rider)

    def start(self) -> None:
        """Transition to RUNNING and launch all processes."""
        old_state = self._state
        self._state = SimulationState.RUNNING
        self._emit_control_event("simulation.started", old_state, "user_request")
        self._start_agent_processes()
        self._start_periodic_processes()

    def stop(self) -> None:
        """Transition to STOPPED and halt all processes."""
        self.transition_state(SimulationState.STOPPED)

    def step(self, seconds: int) -> None:
        """Advance simulation by specified seconds."""
        # Start processes for any pending agents (thread-safe approach)
        self._start_pending_agents()

        # Start any pending trip executions (thread-safe approach for matches made from async context)
        if hasattr(self._matching_server, "start_pending_trip_executions"):
            self._matching_server.start_pending_trip_executions()

        target_time = self._env.now + seconds

        if self._speed_multiplier == 100:
            self._env.run(until=target_time)
            return

        start_wall = time.perf_counter()
        start_sim = self._env.now
        step_size = seconds

        while self._env.now < target_time:
            next_step = min(self._env.now + step_size, target_time)
            self._env.run(until=next_step)

            elapsed_wall = time.perf_counter() - start_wall
            elapsed_sim = self._env.now - start_sim
            target_wall = elapsed_sim / self._speed_multiplier
            sleep_time = target_wall - elapsed_wall

            if sleep_time > 0.01:
                time.sleep(sleep_time)

    def set_speed(self, multiplier: int) -> None:
        """Change simulation speed (any positive integer)."""
        if multiplier < 1:
            raise ValueError("Speed multiplier must be a positive integer")

        previous_speed = self._speed_multiplier
        self._speed_multiplier = multiplier

        if self._kafka_producer:
            event = {
                "event_id": str(uuid4()),
                "event_type": "simulation.speed_changed",
                "timestamp": self._time_manager.format_timestamp(),
                "previous_state": self._state.value,
                "new_state": self._state.value,
                "speed_multiplier": multiplier,
                "trigger": "user_request",
                "previous_speed": previous_speed,
                "new_speed": multiplier,
                "active_drivers": self.active_driver_count,
                "active_riders": self.active_rider_count,
                "in_flight_trips": len(self._get_in_flight_trips()),
            }
            self._kafka_producer.produce(
                topic="simulation-control",
                key="engine",
                value=event,
            )

    def pause(self) -> None:
        """Initiate two-phase pause: RUNNING -> DRAINING -> PAUSED."""
        if SimulationState.DRAINING not in VALID_STATE_TRANSITIONS.get(self._state, set()):
            raise ValueError(f"Invalid state transition from {self._state.value} to draining")

        old_state = self._state
        self._state = SimulationState.DRAINING
        self._emit_control_event("simulation.draining", old_state, "user_request")
        self._drain_process = self._env.process(self._run_drain_process())  # type: ignore[no-untyped-call]

    def resume(self) -> None:
        """Transition from PAUSED to RUNNING."""
        if SimulationState.RUNNING not in VALID_STATE_TRANSITIONS.get(self._state, set()):
            raise ValueError(f"Invalid state transition from {self._state.value} to running")

        old_state = self._state
        self._state = SimulationState.RUNNING
        self._emit_control_event("simulation.resumed", old_state, "user_request")
        self._start_agent_processes()
        self._start_periodic_processes()

    def current_time(self) -> datetime:
        """Get current simulated time as datetime."""
        return self._time_manager.current_time()

    def try_restore_from_checkpoint(self) -> bool:
        """Attempt to restore simulation state from a checkpoint.

        Uses the configured checkpoint backend (SQLite or S3) based on
        settings.simulation.checkpoint_storage_type. Currently only
        SQLite supports full engine restoration; S3 checkpoint saving
        works but restoration requires a future implementation.

        Returns:
            True if successfully restored, False if no checkpoint found or restore failed
        """
        from db.checkpoint import CheckpointError, CheckpointManager

        settings = get_settings()
        storage_type = settings.simulation.checkpoint_storage_type

        if storage_type == "s3":
            logger.warning(
                "S3 checkpoint restore not yet implemented. "
                "S3 backend supports saving checkpoints; "
                "restoration will be added in a future update."
            )
            return False

        if self._sqlite_db is None:
            return False

        try:
            with self._sqlite_db() as session:
                checkpoint_manager = CheckpointManager(session)
                if not checkpoint_manager.has_checkpoint():
                    return False
                checkpoint_manager.restore_to_engine(self)
                self._time_manager = TimeManager(
                    self._time_manager._simulation_start_time,
                    self._env,
                )
                return True
        except CheckpointError as e:
            logger.warning("Checkpoint restore failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during checkpoint restore: %s", e)
            return False

    def save_checkpoint(self) -> None:
        """Save current simulation state to a checkpoint.

        Uses the configured checkpoint backend (SQLite or S3) based on
        settings.simulation.checkpoint_storage_type.
        """
        from db import get_checkpoint_manager

        settings = get_settings()
        storage_type = settings.simulation.checkpoint_storage_type

        if storage_type == "sqlite":
            if self._sqlite_db is None:
                return
            with self._sqlite_db() as session:
                checkpoint_manager = get_checkpoint_manager(settings, session=session)
                checkpoint_manager.save_from_engine(self)
                session.commit()
        else:
            checkpoint_manager = get_checkpoint_manager(settings)
            checkpoint_manager.save_from_engine(self)

    async def request_match(
        self,
        rider_id: str,
        pickup_location: tuple[float, float],
        dropoff_location: tuple[float, float],
        pickup_zone_id: str,
        dropoff_zone_id: str,
        surge_multiplier: float,
        fare: float,
        trip_id: str | None = None,
    ) -> "Trip | None":
        """Delegate to matching server."""
        if self._state in {SimulationState.DRAINING, SimulationState.PAUSED}:
            raise ValueError("Simulation is pausing")

        return await self._matching_server.request_match(
            rider_id=rider_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
            trip_id=trip_id,
        )

    def _start_agent_processes(self) -> None:
        """Launch all registered agent run() processes."""
        for driver in self._active_drivers.values():
            process = self._env.process(driver.run())
            self._agent_processes.add(process)
            driver._process_started = True  # type: ignore[attr-defined]

        for rider in self._active_riders.values():
            process = self._env.process(rider.run())
            self._agent_processes.add(process)
            rider._process_started = True  # type: ignore[attr-defined]

        # All agents now have processes — clear the pending queue
        self._pending_agents.clear()

    def _start_pending_agents(self) -> None:
        """Start run() processes for agents in the pending queue.

        Drains _pending_agents via popleft() — O(1) in steady state when
        no new agents have been registered since the last call.
        """
        while self._pending_agents:
            agent = self._pending_agents.popleft()
            process = self._env.process(agent.run())
            self._agent_processes.add(process)
            object.__setattr__(agent, "_process_started", True)

    def _start_periodic_processes(self) -> None:
        """Start surge updates and agent spawner processes.

        Note: GPS pings are handled by each driver's own _emit_gps_ping() process
        which tracks all relevant statuses accurately (online, en_route_pickup, en_route_destination).
        """
        surge_process = self._env.process(self._surge_update_process())  # type: ignore[no-untyped-call]
        self._periodic_processes.append(surge_process)

        # Start 4 agent spawner processes (per-mode) for continuous spawning
        settings = get_settings()

        # Driver immediate: 2/s = 0.5s interval
        driver_imm = self._env.process(
            self._spawner_process(  # type: ignore[no-untyped-call]
                lambda: (
                    self._agent_factory.dequeue_driver_immediate() if self._agent_factory else False
                ),
                lambda: self._spawn_single_driver(immediate_online=True),
                1.0 / settings.spawn.driver_immediate_spawn_rate,
            )
        )
        self._periodic_processes.append(driver_imm)

        # Driver scheduled: 10/s = 0.1s interval
        driver_sched = self._env.process(
            self._spawner_process(  # type: ignore[no-untyped-call]
                lambda: (
                    self._agent_factory.dequeue_driver_scheduled() if self._agent_factory else False
                ),
                lambda: self._spawn_single_driver(immediate_online=False),
                1.0 / settings.spawn.driver_scheduled_spawn_rate,
            )
        )
        self._periodic_processes.append(driver_sched)

        # Rider immediate: 2/s = 0.5s interval
        rider_imm = self._env.process(
            self._spawner_process(  # type: ignore[no-untyped-call]
                lambda: (
                    self._agent_factory.dequeue_rider_immediate() if self._agent_factory else False
                ),
                lambda: self._spawn_single_rider(immediate_first_trip=True),
                1.0 / settings.spawn.rider_immediate_spawn_rate,
            )
        )
        self._periodic_processes.append(rider_imm)

        # Rider scheduled: 10/s = 0.1s interval
        rider_sched = self._env.process(
            self._spawner_process(  # type: ignore[no-untyped-call]
                lambda: (
                    self._agent_factory.dequeue_rider_scheduled() if self._agent_factory else False
                ),
                lambda: self._spawn_single_rider(immediate_first_trip=False),
                1.0 / settings.spawn.rider_scheduled_spawn_rate,
            )
        )
        self._periodic_processes.append(rider_sched)

        if settings.simulation.checkpoint_enabled:
            checkpoint_proc = self._env.process(self._checkpoint_process())  # type: ignore[no-untyped-call]
            self._periodic_processes.append(checkpoint_proc)

    def _surge_update_process(self):  # type: ignore[no-untyped-def]
        """Recalculate surge every 60 simulated seconds.

        Note: Per-zone SurgeUpdateEvent events with full schema compliance
        are emitted by SurgePricingCalculator in surge_pricing.py.
        """
        while True:
            if hasattr(self._matching_server, "update_surge_pricing"):
                self._matching_server.update_surge_pricing()

            yield self._env.timeout(60)

    def _checkpoint_process(self):  # type: ignore[no-untyped-def]
        """Periodically save simulation checkpoint."""
        settings = get_settings()
        interval = settings.simulation.checkpoint_interval
        while True:
            yield self._env.timeout(interval)
            try:
                self.save_checkpoint()
                logger.info("Periodic checkpoint saved at sim_time=%.1f", self._env.now)
            except Exception:
                logger.exception("Periodic checkpoint failed")

    def _spawner_process(self, dequeue_fn, spawn_fn, interval):  # type: ignore[no-untyped-def]
        """Generic spawner for any queue/mode combination.

        Args:
            dequeue_fn: Callable that returns True if an agent was dequeued, False otherwise
            spawn_fn: Callable to spawn the agent
            interval: Time between spawn attempts (1/rate)
        """
        while True:
            if self._state == SimulationState.RUNNING and dequeue_fn():
                spawn_fn()
            yield self._env.timeout(interval)

    def _spawn_single_driver(self, immediate_online: bool = True) -> str | None:
        """Spawn a single driver and start its process immediately.

        Args:
            immediate_online: If True, go online immediately; if False, follow DNA shift_preference

        Returns:
            The driver_id if spawned, None if factory not available
        """
        if self._agent_factory is None:
            return None

        from agents.dna_generator import generate_driver_dna
        from agents.driver_agent import DriverAgent

        dna = generate_driver_dna()
        driver_id = str(uuid4())

        # Get dependencies from factory
        agent = DriverAgent(
            driver_id=driver_id,
            dna=dna,
            env=self._env,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_client,
            driver_repository=None,
            registry_manager=self._agent_factory._registry_manager,
            zone_loader=self._agent_factory._zone_loader,
            immediate_online=immediate_online,
            simulation_engine=self,
        )

        self.register_driver(agent)

        if self._agent_factory._registry_manager:
            self._agent_factory._registry_manager.register_driver(agent)

        # Drain pending queue to start the agent's process immediately
        self._start_pending_agents()

        return driver_id

    def _spawn_single_rider(self, immediate_first_trip: bool = False) -> str | None:
        """Spawn a single rider and start its process immediately.

        Args:
            immediate_first_trip: If True, request trip immediately; if False, follow DNA schedule

        Returns:
            The rider_id if spawned, None if factory not available
        """
        if self._agent_factory is None:
            return None

        from agents.dna_generator import generate_rider_dna
        from agents.rider_agent import RiderAgent

        dna = generate_rider_dna()
        rider_id = str(uuid4())

        # Get dependencies from factory
        agent = RiderAgent(
            rider_id=rider_id,
            dna=dna,
            env=self._env,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_client,
            rider_repository=None,
            simulation_engine=self,
            zone_loader=self._agent_factory._zone_loader,
            osrm_client=self._agent_factory._osrm_client,
            surge_calculator=self._agent_factory._surge_calculator,
            immediate_first_trip=immediate_first_trip,
        )

        self.register_rider(agent)

        if self._agent_factory._registry_manager:
            self._agent_factory._registry_manager.register_rider(agent)

        # Drain pending queue to start the agent's process immediately
        self._start_pending_agents()

        return rider_id

    def _get_in_flight_trips(self) -> list["Trip"]:
        """Get trips in non-terminal states from MatchingServer."""
        if hasattr(self._matching_server, "get_active_trips"):
            trips = self._matching_server.get_active_trips()
            # Handle mock objects in tests
            if isinstance(trips, list):
                return trips
        return []

    def _run_drain_process(self):  # type: ignore[no-untyped-def]
        """Monitor quiescence and transition to PAUSED."""
        timeout_at = self._env.now + 7200
        trigger = "quiescence_achieved"

        while True:
            in_flight = self._get_in_flight_trips()
            if len(in_flight) == 0:
                trigger = "quiescence_achieved"
                break

            if self._env.now >= timeout_at:
                trigger = "drain_timeout"
                self._force_cancel_trips(in_flight)
                break

            yield self._env.timeout(5)

        self._transition_to_paused(trigger)

    def _force_cancel_trips(self, trips: list["Trip"]) -> None:
        """Force-cancel all in-flight trips."""
        from db.repositories.trip_repository import TripRepository
        from events.schemas import TripEvent
        from trip import TripState

        with self._sqlite_db() as session:
            repo = TripRepository(session)
            for trip in trips:
                self._force_cancel_trip(trip)
                repo.update_state(
                    trip_id=trip.trip_id,
                    new_state=TripState.CANCELLED,
                    cancelled_by="system",
                    cancellation_reason="system_pause",
                    cancellation_stage=trip.state.name.lower(),
                )

                if self._kafka_producer:
                    event = TripEvent(
                        event_type="trip.cancelled",
                        trip_id=trip.trip_id,
                        rider_id=trip.rider_id,
                        driver_id=trip.driver_id,
                        pickup_location=trip.pickup_location,
                        dropoff_location=trip.dropoff_location,
                        pickup_zone_id=trip.pickup_zone_id,
                        dropoff_zone_id=trip.dropoff_zone_id,
                        surge_multiplier=trip.surge_multiplier,
                        fare=trip.fare,
                        cancelled_by="system",
                        cancellation_reason="system_pause",
                        cancellation_stage=trip.state.name.lower(),
                        timestamp=self._time_manager.format_timestamp(),
                    )
                    self._kafka_producer.produce(
                        topic="trips",
                        key=trip.trip_id,
                        value=event.model_dump_json(),
                    )
            session.commit()

    def _force_cancel_trip(self, trip: "Trip") -> None:
        """Cancel a single trip with system metadata."""
        trip.cancel(by="system", reason="system_pause", stage=trip.state.name.lower())

    def _transition_to_paused(self, trigger: str) -> None:
        """Complete pause sequence, emit event, and save checkpoint."""
        old_state = self._state
        self._state = SimulationState.PAUSED
        self._emit_control_event("simulation.paused", old_state, trigger)

        settings = get_settings()
        if settings.simulation.checkpoint_enabled:
            try:
                self.save_checkpoint()
                logger.info("Checkpoint saved on pause (trigger=%s)", trigger)
            except Exception:
                logger.exception("Checkpoint on pause failed")

    def _emit_control_event(
        self, event_type: str, old_state: SimulationState, trigger: str
    ) -> None:
        """Emit simulation control event."""
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": self._time_manager.format_timestamp(),
            "previous_state": old_state.value,
            "new_state": self._state.value,
            "speed_multiplier": self._speed_multiplier,
            "trigger": trigger,
            "active_drivers": self.active_driver_count,
            "active_riders": self.active_rider_count,
            "in_flight_trips": len(self._get_in_flight_trips()),
        }

        self._kafka_producer.produce(
            topic="simulation-control",
            key="engine",
            value=event,
        )

    def reset(self) -> None:
        """Reset simulation to clean initial state, clearing all data."""
        old_state = self._state

        # Stop if running
        if self._state != SimulationState.STOPPED:
            self._state = SimulationState.STOPPED

        # Clear agent registries
        self._active_drivers.clear()
        self._active_riders.clear()
        self._pending_agents.clear()
        self._agent_processes.clear()
        self._periodic_processes.clear()
        self._active_driver_counter = 0
        self._active_rider_counter = 0
        self._drain_process = None

        # Create fresh SimPy environment
        self._env = simpy.Environment()

        # Reset time manager with fresh env
        simulation_start_time = datetime.now(UTC)
        self._time_manager = TimeManager(simulation_start_time, self._env)

        # Generate new session ID for the fresh simulation run
        self._session_id = str(uuid4())
        setup_correlation_logging(self._session_id)

        # Clear matching server state and update its environment reference
        if hasattr(self._matching_server, "clear"):
            self._matching_server.clear()
        # Update matching server's environment reference to the new one
        if hasattr(self._matching_server, "_env"):
            self._matching_server._env = self._env

        # Clear spawn queues
        if self._agent_factory:
            self._agent_factory.clear_spawn_queues()

        # Clear database
        if self._sqlite_db:
            self._clear_database()

        # Emit reset event
        self._emit_control_event("simulation.reset", old_state, "user_request")

    def _clear_database(self) -> None:
        """Clear all simulation data from SQLite."""
        from sqlalchemy import text

        with self._sqlite_db() as session:
            # Clear all tables
            session.execute(text("DELETE FROM trips"))
            session.execute(text("DELETE FROM drivers"))
            session.execute(text("DELETE FROM riders"))
            session.execute(text("DELETE FROM route_cache"))
            session.execute(text("DELETE FROM simulation_metadata"))
            session.commit()
