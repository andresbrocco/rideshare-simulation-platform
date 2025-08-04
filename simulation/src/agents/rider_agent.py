"""Rider agent base class for SimPy simulation."""

import random
from collections.abc import Generator
from datetime import UTC, datetime

import simpy

from agents.dna import RiderDNA
from agents.event_emitter import GPS_PING_INTERVAL, EventEmitter
from events.schemas import GPSPingEvent, RiderProfileEvent
from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher


class RiderAgent(EventEmitter):
    """SimPy process representing a rider with DNA-based behavior."""

    def __init__(
        self,
        rider_id: str,
        dna: RiderDNA,
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None = None,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._rider_id = rider_id
        self._dna = dna
        self._env = env

        # Runtime state
        self._status = "idle"
        self._location: tuple[float, float] | None = None
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0

        self._emit_creation_event()

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

    def _emit_creation_event(self) -> None:
        """Emit rider.created event on initialization."""
        import asyncio

        event = RiderProfileEvent(
            event_type="rider.created",
            rider_id=self._rider_id,
            timestamp=datetime.now(UTC).isoformat(),
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=self._dna.email,
            phone=self._dna.phone,
            home_location=self._dna.home_location,
            payment_method_type=self._dna.payment_method_type,
            payment_method_masked=self._dna.payment_method_masked,
            behavior_factor=self._dna.behavior_factor,
        )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._emit_event(
                        event=event,
                        kafka_topic="rider-profiles",
                        partition_key=self._rider_id,
                        redis_channel="rider-updates",
                    )
                )
            else:
                loop.run_until_complete(
                    self._emit_event(
                        event=event,
                        kafka_topic="rider-profiles",
                        partition_key=self._rider_id,
                        redis_channel="rider-updates",
                    )
                )
        except RuntimeError:
            asyncio.run(
                self._emit_event(
                    event=event,
                    kafka_topic="rider-profiles",
                    partition_key=self._rider_id,
                    redis_channel="rider-updates",
                )
            )

    def run(self) -> Generator[simpy.Event]:
        """SimPy process entry point with GPS ping loop."""
        import asyncio

        while True:
            if self._status == "in_trip":
                if self._location:
                    event = GPSPingEvent(
                        entity_type="rider",
                        entity_id=self._rider_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        location=self._location,
                        heading=None,
                        speed=None,
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
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                        else:
                            loop.run_until_complete(
                                self._emit_event(
                                    event=event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                    except RuntimeError:
                        asyncio.run(
                            self._emit_event(
                                event=event,
                                kafka_topic="gps-pings",
                                partition_key=self._rider_id,
                                redis_channel="rider-updates",
                            )
                        )

                yield self._env.timeout(GPS_PING_INTERVAL)
            else:
                yield self._env.timeout(GPS_PING_INTERVAL)
