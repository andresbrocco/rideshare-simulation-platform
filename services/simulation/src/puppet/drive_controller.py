"""Controller for puppet driver movement along routes."""

import logging
import random
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from events.schemas import GPSPingEvent
from geo.gps_simulation import GPSSimulator

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from engine import SimulationEngine
    from geo.osrm_client import RouteResponse
    from kafka.producer import KafkaProducer
    from redis_client.publisher import RedisPublisher
    from trip import Trip

logger = logging.getLogger(__name__)


class PuppetDriveController:
    """Controls puppet driver movement along OSRM routes.

    Runs movement in a background thread, emitting GPS updates
    at regular intervals. Designed for API-controlled puppet agents
    that operate outside the SimPy simulation loop.
    """

    def __init__(
        self,
        driver: "DriverAgent",
        trip: "Trip",
        route_response: "RouteResponse",
        kafka_producer: "KafkaProducer | None",
        redis_publisher: "RedisPublisher | None",
        speed_multiplier: float = 1.0,
        gps_interval_seconds: float = 1.0,
        is_pickup_drive: bool = True,
        simulation_engine: "SimulationEngine | None" = None,
    ):
        self._driver = driver
        self._trip = trip
        self._route = route_response
        self._kafka_producer = kafka_producer
        self._redis_publisher = redis_publisher
        self._speed_multiplier = max(0.0625, speed_multiplier)
        self._gps_interval = gps_interval_seconds
        self._is_pickup_drive = is_pickup_drive
        self._simulation_engine = simulation_engine

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._completed = False
        self._completion_callbacks: list[Callable[[], None]] = []

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_completed(self) -> bool:
        return self._completed

    def on_completion(self, callback: Callable[[], None]) -> None:
        """Register callback to be called when drive completes."""
        self._completion_callbacks.append(callback)

    def _resolve_rider(self) -> "RiderAgent | None":
        """Resolve the rider for this trip during destination drives.

        During the destination leg the rider is physically in the car,
        so their location should mirror the driver's position.
        Returns None for pickup drives (rider is still at pickup location).
        """
        if self._is_pickup_drive or not self._simulation_engine:
            return None
        return self._simulation_engine._active_riders.get(self._trip.rider_id)

    def start(self) -> None:
        """Start the drive in a background thread."""
        if self.is_running:
            raise RuntimeError("Drive already in progress")

        self._stop_event.clear()
        self._completed = False
        self._thread = threading.Thread(
            target=self._drive_loop,
            name=f"puppet-drive-{self._driver.driver_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the drive early (e.g., for cancellation)."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _drive_loop(self) -> None:
        """Main drive loop running in background thread."""
        geometry = self._route.geometry
        duration = self._route.duration_seconds

        # Adjust for speed multiplier (faster simulation = shorter real time)
        real_duration = duration / self._speed_multiplier
        real_interval = self._gps_interval / self._speed_multiplier

        num_intervals = max(1, int(real_duration / real_interval))

        logger.info(
            f"Puppet drive starting: driver={self._driver.driver_id}, "
            f"duration={duration}s (real={real_duration:.1f}s), "
            f"intervals={num_intervals}, is_pickup={self._is_pickup_drive}"
        )

        gps_simulator = GPSSimulator(noise_meters=0)

        # Resolve rider once — during destination drives the rider moves with the driver
        rider = self._resolve_rider()

        for i in range(num_intervals):
            if self._stop_event.is_set():
                logger.info(f"Puppet drive stopped early: {self._driver.driver_id}")
                return

            # Calculate position along route
            progress = (i + 1) / num_intervals
            idx = int(progress * (len(geometry) - 1))
            current_pos = geometry[min(idx, len(geometry) - 1)]

            # Calculate heading
            next_idx = min(idx + 1, len(geometry) - 1)
            if idx != next_idx:
                heading = gps_simulator.calculate_heading(current_pos, geometry[next_idx])
            else:
                heading = self._driver.heading or 0.0

            # Update driver location
            self._driver.update_location(*current_pos, heading=heading)

            # Mirror position to rider during destination leg
            if rider:
                rider.update_location(*current_pos)

            # Update route progress on trip
            if self._is_pickup_drive:
                self._trip.pickup_route_progress_index = idx
            else:
                self._trip.route_progress_index = idx

            # Emit GPS ping
            self._emit_gps_ping(current_pos, heading)

            # Sleep for interval
            time.sleep(real_interval)

        # Ensure final position is exactly at destination
        final_pos = geometry[-1]
        self._driver.update_location(*final_pos)
        if rider:
            rider.update_location(*final_pos)
        self._emit_gps_ping(final_pos, self._driver.heading or 0.0)

        # Mark complete and run callbacks
        self._completed = True
        logger.info(f"Puppet drive completed: {self._driver.driver_id}")

        for callback in self._completion_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Drive completion callback error: {e}")

    def _emit_gps_ping(self, location: tuple[float, float], heading: float) -> None:
        """Emit GPS ping to Kafka and Redis."""
        timestamp = (
            self._simulation_engine.time_manager.format_timestamp()
            if self._simulation_engine
            else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        event = GPSPingEvent(
            entity_type="driver",
            entity_id=self._driver.driver_id,
            timestamp=timestamp,
            location=location,
            heading=heading,
            speed=random.uniform(20, 60),  # Approximate city speed
            accuracy=5.0,
            trip_id=self._trip.trip_id,
            pickup_route_progress_index=(
                self._trip.pickup_route_progress_index if self._is_pickup_drive else None
            ),
            route_progress_index=(
                self._trip.route_progress_index if not self._is_pickup_drive else None
            ),
        )

        if self._kafka_producer:
            try:
                self._kafka_producer.produce(
                    topic="gps_pings",
                    key=self._driver.driver_id,
                    value=event,
                )
            except Exception as e:
                logger.warning(f"Failed to publish GPS ping to Kafka: {e}")
