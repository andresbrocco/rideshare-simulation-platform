"""Driver agent base class for SimPy simulation."""

import json
import logging
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import simpy

from agents.dna import DriverDNA
from agents.event_emitter import GPS_PING_INTERVAL, EventEmitter
from events.schemas import DriverProfileEvent, GPSPingEvent
from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher

if TYPE_CHECKING:
    from db.repositories.driver_repository import DriverRepository

logger = logging.getLogger(__name__)


class DriverAgent(EventEmitter):
    """SimPy process representing a driver with DNA-based behavior."""

    def __init__(
        self,
        driver_id: str,
        dna: DriverDNA,
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None = None,
        driver_repository: "DriverRepository | None" = None,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._driver_id = driver_id
        self._dna = dna
        self._env = env
        self._driver_repository = driver_repository

        # Runtime state
        self._status = "offline"
        self._location: tuple[float, float] | None = None
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0

        if self._driver_repository:
            try:
                self._driver_repository.create(driver_id, dna)
            except Exception as e:
                logger.error(f"Failed to persist driver {driver_id} on creation: {e}")

        self._emit_creation_event()

    @property
    def driver_id(self) -> str:
        return self._driver_id

    @property
    def dna(self) -> DriverDNA:
        return self._dna

    @property
    def status(self) -> str:
        return self._status

    @property
    def location(self) -> tuple[float, float] | None:
        return self._location

    @property
    def active_trip(self) -> str | None:
        return self._active_trip

    @property
    def current_rating(self) -> float:
        return self._current_rating

    @property
    def rating_count(self) -> int:
        return self._rating_count

    def go_online(self) -> None:
        """Transition from offline to online."""
        previous_status = self._status
        self._status = "online"

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "go_online")

    def go_offline(self) -> None:
        """Transition to offline."""
        previous_status = self._status
        self._status = "offline"

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "go_offline")

    def accept_trip(self, trip_id: str) -> None:
        """Accept a trip offer, transition to busy."""
        previous_status = self._status
        self._status = "busy"
        self._active_trip = trip_id

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
                self._driver_repository.update_active_trip(self._driver_id, trip_id)
            except Exception as e:
                logger.error(f"Failed to persist trip acceptance for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "accept_trip")

    def start_pickup(self) -> None:
        """Start driving to pickup location."""
        previous_status = self._status
        self._status = "en_route_pickup"

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "start_pickup")

    def start_trip(self) -> None:
        """Start the trip after rider pickup."""
        previous_status = self._status
        self._status = "en_route_destination"

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "start_trip")

    def complete_trip(self) -> None:
        """Complete the trip and return to online."""
        previous_status = self._status
        self._status = "online"
        self._active_trip = None

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
                self._driver_repository.update_active_trip(self._driver_id, None)
            except Exception as e:
                logger.error(f"Failed to persist trip completion for driver {self._driver_id}: {e}")

        self._emit_status_event(previous_status, self._status, "complete_trip")

    def update_location(self, lat: float, lon: float) -> None:
        """Update current location without emitting event."""
        self._location = (lat, lon)

        if self._driver_repository:
            try:
                self._driver_repository.update_location(self._driver_id, (lat, lon))
            except Exception as e:
                logger.error(f"Failed to persist location for driver {self._driver_id}: {e}")

    def update_rating(self, new_rating: int) -> None:
        """Update rolling average rating."""
        self._current_rating = (self._current_rating * self._rating_count + new_rating) / (
            self._rating_count + 1
        )
        self._rating_count += 1

        if self._driver_repository:
            try:
                self._driver_repository.update_rating(
                    self._driver_id, self._current_rating, self._rating_count
                )
            except Exception as e:
                logger.error(f"Failed to persist rating for driver {self._driver_id}: {e}")

    def _emit_creation_event(self) -> None:
        """Emit driver.created event on initialization."""
        import asyncio

        event = DriverProfileEvent(
            event_type="driver.created",
            driver_id=self._driver_id,
            timestamp=datetime.now(UTC).isoformat(),
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=self._dna.email,
            phone=self._dna.phone,
            home_location=self._dna.home_location,
            preferred_zones=self._dna.preferred_zones,
            shift_preference=self._dna.shift_preference.value,
            vehicle_make=self._dna.vehicle_make,
            vehicle_model=self._dna.vehicle_model,
            vehicle_year=self._dna.vehicle_year,
            license_plate=self._dna.license_plate,
        )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._emit_event(
                        event=event,
                        kafka_topic="driver-profiles",
                        partition_key=self._driver_id,
                        redis_channel="driver-updates",
                    )
                )
            else:
                loop.run_until_complete(
                    self._emit_event(
                        event=event,
                        kafka_topic="driver-profiles",
                        partition_key=self._driver_id,
                        redis_channel="driver-updates",
                    )
                )
        except RuntimeError:
            asyncio.run(
                self._emit_event(
                    event=event,
                    kafka_topic="driver-profiles",
                    partition_key=self._driver_id,
                    redis_channel="driver-updates",
                )
            )

    def _emit_status_event(self, previous_status: str, new_status: str, trigger: str) -> None:
        """Emit driver status event to Kafka."""
        if self._kafka_producer is None:
            return

        event = {
            "event_id": str(uuid4()),
            "driver_id": self._driver_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_status": previous_status,
            "new_status": new_status,
            "trigger": trigger,
            "location": list(self._location) if self._location else [0.0, 0.0],
        }

        self._kafka_producer.produce(
            topic="driver-status",
            key=self._driver_id,
            value=json.dumps(event),
        )

    def run(self) -> Generator[simpy.Event]:
        """SimPy process entry point with GPS ping loop."""
        import asyncio

        while True:
            if self._status in ("online", "busy", "en_route_pickup", "en_route_destination"):
                if self._location:
                    event = GPSPingEvent(
                        entity_type="driver",
                        entity_id=self._driver_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        location=self._location,
                        heading=random.uniform(0, 360),
                        speed=random.uniform(20, 60),
                        accuracy=5.0,
                        trip_id=self._active_trip,
                    )

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(
                                self._emit_event(
                                    event=event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._driver_id,
                                    redis_channel="driver-updates",
                                )
                            )
                        else:
                            loop.run_until_complete(
                                self._emit_event(
                                    event=event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._driver_id,
                                    redis_channel="driver-updates",
                                )
                            )
                    except RuntimeError:
                        asyncio.run(
                            self._emit_event(
                                event=event,
                                kafka_topic="gps-pings",
                                partition_key=self._driver_id,
                                redis_channel="driver-updates",
                            )
                        )

                yield self._env.timeout(GPS_PING_INTERVAL)
            else:
                yield self._env.timeout(GPS_PING_INTERVAL)

    @classmethod
    def from_database(
        cls,
        driver_id: str,
        driver_repository: "DriverRepository",
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None = None,
    ) -> "DriverAgent":
        """Load driver agent from database."""
        driver = driver_repository.get(driver_id)
        if driver is None:
            raise ValueError(f"Driver {driver_id} not found in database")

        dna = DriverDNA.model_validate_json(driver.dna_json)

        agent = cls.__new__(cls)
        EventEmitter.__init__(agent, kafka_producer, redis_publisher)

        agent._driver_id = driver_id
        agent._dna = dna
        agent._env = env
        agent._driver_repository = driver_repository

        agent._status = driver.status
        lat, lon = map(float, driver.current_location.split(","))
        agent._location = (lat, lon)
        agent._active_trip = driver.active_trip
        agent._current_rating = driver.current_rating
        agent._rating_count = driver.rating_count

        return agent
