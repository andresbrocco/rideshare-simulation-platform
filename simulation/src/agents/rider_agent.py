"""Rider agent base class for SimPy simulation."""

import logging
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import simpy

from agents.dna import RiderDNA
from agents.event_emitter import GPS_PING_INTERVAL, EventEmitter
from events.schemas import GPSPingEvent, RiderProfileEvent
from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher

if TYPE_CHECKING:
    from db.repositories.rider_repository import RiderRepository

logger = logging.getLogger(__name__)


class RiderAgent(EventEmitter):
    """SimPy process representing a rider with DNA-based behavior."""

    def __init__(
        self,
        rider_id: str,
        dna: RiderDNA,
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None = None,
        rider_repository: "RiderRepository | None" = None,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._rider_id = rider_id
        self._dna = dna
        self._env = env
        self._rider_repository = rider_repository

        # Runtime state
        self._status = "idle"
        self._location: tuple[float, float] | None = None
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0

        if self._rider_repository:
            try:
                self._rider_repository.create(rider_id, dna)
            except Exception as e:
                logger.error(f"Failed to persist rider {rider_id} on creation: {e}")

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

        if self._rider_repository:
            try:
                self._rider_repository.update_status(self._rider_id, self._status)
                self._rider_repository.update_active_trip(self._rider_id, trip_id)
            except Exception as e:
                logger.error(f"Failed to persist trip request for rider {self._rider_id}: {e}")

    def start_trip(self) -> None:
        """Transition from waiting to in_trip."""
        self._status = "in_trip"

        if self._rider_repository:
            try:
                self._rider_repository.update_status(self._rider_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for rider {self._rider_id}: {e}")

    def complete_trip(self) -> None:
        """Transition from in_trip to idle, clear active trip."""
        self._status = "idle"
        self._active_trip = None

        if self._rider_repository:
            try:
                self._rider_repository.update_status(self._rider_id, self._status)
                self._rider_repository.update_active_trip(self._rider_id, None)
            except Exception as e:
                logger.error(f"Failed to persist trip completion for rider {self._rider_id}: {e}")

    def cancel_trip(self) -> None:
        """Transition from waiting to idle, clear active trip."""
        self._status = "idle"
        self._active_trip = None

        if self._rider_repository:
            try:
                self._rider_repository.update_status(self._rider_id, self._status)
                self._rider_repository.update_active_trip(self._rider_id, None)
            except Exception as e:
                logger.error(f"Failed to persist trip cancellation for rider {self._rider_id}: {e}")

    def update_location(self, lat: float, lon: float) -> None:
        """Update current location."""
        self._location = (lat, lon)

        if self._rider_repository:
            try:
                self._rider_repository.update_location(self._rider_id, (lat, lon))
            except Exception as e:
                logger.error(f"Failed to persist location for rider {self._rider_id}: {e}")

    def update_rating(self, new_rating: int) -> None:
        """Update rolling average rating."""
        self._current_rating = (self._current_rating * self._rating_count + new_rating) / (
            self._rating_count + 1
        )
        self._rating_count += 1

        if self._rider_repository:
            try:
                self._rider_repository.update_rating(
                    self._rider_id, self._current_rating, self._rating_count
                )
            except Exception as e:
                logger.error(f"Failed to persist rating for rider {self._rider_id}: {e}")

    def select_destination(self) -> tuple[float, float]:
        """Select destination based on location and time with weighted probabilities."""
        from agents.dna import haversine_distance

        at_home = False
        if self._location:
            distance_to_home = haversine_distance(
                self._location[0],
                self._location[1],
                self._dna.home_location[0],
                self._dna.home_location[1],
            )
            at_home = distance_to_home < 0.1

        if at_home:
            choice = random.random()
            if choice < 0.8:
                return self._select_weighted_frequent_destination()
            else:
                return self._generate_random_location()
        else:
            choice = random.random()
            if choice < 0.6:
                return self._dna.home_location
            elif choice < 0.9:
                return self._select_weighted_frequent_destination()
            else:
                return self._generate_random_location()

    def _select_weighted_frequent_destination(self) -> tuple[float, float]:
        """Select from frequent destinations with time affinity weighting."""
        destinations = self._dna.frequent_destinations
        current_hour = int((self._env.now % 86400) / 3600)

        weights = []
        for dest in destinations:
            weight = dest["weight"]
            if dest.get("time_affinity") and current_hour in dest["time_affinity"]:
                weight *= 2
            weights.append(weight)

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        selected = random.choices(destinations, weights=normalized_weights, k=1)[0]
        return tuple(selected["coordinates"])

    def _generate_random_location(self) -> tuple[float, float]:
        """Generate random location within Sao Paulo bounds."""
        lat = random.uniform(-23.80, -23.35)
        lon = random.uniform(-46.85, -46.35)
        return (lat, lon)

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
        """SimPy process entry point with request lifecycle."""
        import asyncio
        import uuid

        from events.schemas import TripEvent

        while True:
            if self._status == "in_trip":
                if self._location:
                    gps_event = GPSPingEvent(
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
                                    event=gps_event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                        else:
                            loop.run_until_complete(
                                self._emit_event(
                                    event=gps_event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                    except RuntimeError:
                        asyncio.run(
                            self._emit_event(
                                event=gps_event,
                                kafka_topic="gps-pings",
                                partition_key=self._rider_id,
                                redis_channel="rider-updates",
                            )
                        )

                yield self._env.timeout(GPS_PING_INTERVAL)
                continue

            if self._status != "idle":
                yield self._env.timeout(GPS_PING_INTERVAL)
                continue

            interval_hours = (7 * 24) / self._dna.avg_rides_per_week
            variance = random.uniform(0.8, 1.2)
            wait_time = interval_hours * 3600 * variance

            yield self._env.timeout(wait_time)

            if self._location is None:
                continue

            destination = self.select_destination()
            trip_id = str(uuid.uuid4())

            self.request_trip(trip_id)

            match_timeout = self._env.now + self._dna.patience_threshold

            while self._env.now < match_timeout:
                if self._status == "in_trip":
                    break

                yield self._env.timeout(1)

            if self._status == "waiting":
                self.cancel_trip()

                event = TripEvent(
                    event_type="trip.cancelled",
                    trip_id=trip_id,
                    timestamp=datetime.now(UTC).isoformat(),
                    rider_id=self._rider_id,
                    driver_id=None,
                    pickup_location=self._location,
                    dropoff_location=destination,
                    pickup_zone_id="unknown",
                    dropoff_zone_id="unknown",
                    surge_multiplier=1.0,
                    fare=0.0,
                    cancelled_by="rider",
                    cancellation_reason="patience_timeout",
                )

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self._emit_event(
                                event=event,
                                kafka_topic="trips",
                                partition_key=trip_id,
                                redis_channel="trip-updates",
                            )
                        )
                    else:
                        loop.run_until_complete(
                            self._emit_event(
                                event=event,
                                kafka_topic="trips",
                                partition_key=trip_id,
                                redis_channel="trip-updates",
                            )
                        )
                except RuntimeError:
                    asyncio.run(
                        self._emit_event(
                            event=event,
                            kafka_topic="trips",
                            partition_key=trip_id,
                            redis_channel="trip-updates",
                        )
                    )
                continue

            while self._status == "in_trip":
                if self._location:
                    gps_event = GPSPingEvent(
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
                                    event=gps_event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                        else:
                            loop.run_until_complete(
                                self._emit_event(
                                    event=gps_event,
                                    kafka_topic="gps-pings",
                                    partition_key=self._rider_id,
                                    redis_channel="rider-updates",
                                )
                            )
                    except RuntimeError:
                        asyncio.run(
                            self._emit_event(
                                event=gps_event,
                                kafka_topic="gps-pings",
                                partition_key=self._rider_id,
                                redis_channel="rider-updates",
                            )
                        )

                yield self._env.timeout(GPS_PING_INTERVAL)

    @classmethod
    def from_database(
        cls,
        rider_id: str,
        rider_repository: "RiderRepository",
        env: simpy.Environment,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None = None,
    ) -> "RiderAgent":
        """Load rider agent from database."""
        rider = rider_repository.get(rider_id)
        if rider is None:
            raise ValueError(f"Rider {rider_id} not found in database")

        dna = RiderDNA.model_validate_json(rider.dna_json)

        agent = cls.__new__(cls)
        EventEmitter.__init__(agent, kafka_producer, redis_publisher)

        agent._rider_id = rider_id
        agent._dna = dna
        agent._env = env
        agent._rider_repository = rider_repository

        agent._status = rider.status
        lat, lon = map(float, rider.current_location.split(","))
        agent._location = (lat, lon)
        agent._active_trip = rider.active_trip
        agent._current_rating = rider.current_rating
        agent._rating_count = rider.rating_count

        return agent
