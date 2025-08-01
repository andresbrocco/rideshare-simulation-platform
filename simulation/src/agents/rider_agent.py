"""Rider agent base class for SimPy simulation."""

import random
from collections.abc import Generator

import simpy

from agents.dna import RiderDNA
from kafka.producer import KafkaProducer


class RiderAgent:
    """SimPy process representing a rider with DNA-based behavior."""

    def __init__(
        self,
        rider_id: str,
        dna: RiderDNA,
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
    ):
        self._rider_id = rider_id
        self._dna = dna
        self._env = env
        self._kafka_producer = kafka_producer

        # Runtime state
        self._status = "idle"
        self._location: tuple[float, float] | None = None
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0

    @property
    def rider_id(self) -> str:
        return self._rider_id

    @property
    def dna(self) -> RiderDNA:
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

    def request_trip(self, trip_id: str) -> None:
        """Transition from idle to waiting, set active trip."""
        self._status = "waiting"
        self._active_trip = trip_id

    def start_trip(self) -> None:
        """Transition from waiting to in_trip."""
        self._status = "in_trip"

    def complete_trip(self) -> None:
        """Transition from in_trip to idle, clear active trip."""
        self._status = "idle"
        self._active_trip = None

    def cancel_trip(self) -> None:
        """Transition from waiting to idle, clear active trip."""
        self._status = "idle"
        self._active_trip = None

    def update_location(self, lat: float, lon: float) -> None:
        """Update current location."""
        self._location = (lat, lon)

    def update_rating(self, new_rating: int) -> None:
        """Update rolling average rating."""
        self._current_rating = (self._current_rating * self._rating_count + new_rating) / (
            self._rating_count + 1
        )
        self._rating_count += 1

    def select_destination(self) -> tuple[float, float]:
        """Select destination from DNA frequent destinations using weighted random choice."""
        destinations = self._dna.frequent_destinations
        weights = [d["weight"] for d in destinations]
        selected = random.choices(destinations, weights=weights, k=1)[0]
        return tuple(selected["coordinates"])

    def run(self) -> Generator[simpy.Event]:
        """SimPy process entry point (placeholder for behavior loop)."""
        yield self._env.timeout(0)
