"""Driver agent base class for SimPy simulation."""

import json
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import simpy

from agents.dna import DriverDNA
from kafka.producer import KafkaProducer


class DriverAgent:
    """SimPy process representing a driver with DNA-based behavior."""

    def __init__(
        self,
        driver_id: str,
        dna: DriverDNA,
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
    ):
        self._driver_id = driver_id
        self._dna = dna
        self._env = env
        self._kafka_producer = kafka_producer

        # Runtime state
        self._status = "offline"
        self._location: tuple[float, float] | None = None
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0

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
        self._emit_status_event(previous_status, self._status, "go_online")

    def go_offline(self) -> None:
        """Transition to offline."""
        previous_status = self._status
        self._status = "offline"
        self._emit_status_event(previous_status, self._status, "go_offline")

    def accept_trip(self, trip_id: str) -> None:
        """Accept a trip offer, transition to busy."""
        previous_status = self._status
        self._status = "busy"
        self._active_trip = trip_id
        self._emit_status_event(previous_status, self._status, "accept_trip")

    def start_pickup(self) -> None:
        """Start driving to pickup location."""
        previous_status = self._status
        self._status = "en_route_pickup"
        self._emit_status_event(previous_status, self._status, "start_pickup")

    def start_trip(self) -> None:
        """Start the trip after rider pickup."""
        previous_status = self._status
        self._status = "en_route_destination"
        self._emit_status_event(previous_status, self._status, "start_trip")

    def complete_trip(self) -> None:
        """Complete the trip and return to online."""
        previous_status = self._status
        self._status = "online"
        self._active_trip = None
        self._emit_status_event(previous_status, self._status, "complete_trip")

    def update_location(self, lat: float, lon: float) -> None:
        """Update current location without emitting event."""
        self._location = (lat, lon)

    def update_rating(self, new_rating: int) -> None:
        """Update rolling average rating."""
        self._current_rating = (self._current_rating * self._rating_count + new_rating) / (
            self._rating_count + 1
        )
        self._rating_count += 1

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
        """SimPy process entry point (placeholder for behavior loop)."""
        yield self._env.timeout(0)
