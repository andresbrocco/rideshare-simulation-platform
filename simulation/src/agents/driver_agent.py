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
from agents.rating_logic import generate_rating_value, should_submit_rating
from events.schemas import DriverProfileEvent, GPSPingEvent, RatingEvent
from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher

if TYPE_CHECKING:
    from agents.rider_agent import RiderAgent
    from db.repositories.driver_repository import DriverRepository
    from geo.zones import ZoneLoader
    from matching.agent_registry_manager import AgentRegistryManager
    from trip import Trip

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
        registry_manager: "AgentRegistryManager | None" = None,
        zone_loader: "ZoneLoader | None" = None,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._driver_id = driver_id
        self._dna = dna
        self._env = env
        self._driver_repository = driver_repository
        self._registry_manager = registry_manager
        self._zone_loader = zone_loader

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

        # Set initial random location in São Paulo if not already set
        if self._location is None:
            lat = random.uniform(-23.65, -23.45)
            lon = random.uniform(-46.75, -46.55)
            self._location = (lat, lon)

        if self._driver_repository:
            try:
                self._driver_repository.update_status(self._driver_id, self._status)
            except Exception as e:
                logger.error(f"Failed to persist status for driver {self._driver_id}: {e}")

        # Notify registry manager that driver went online
        if self._registry_manager and self._location:
            zone_id = self._determine_zone(self._location)
            self._registry_manager.driver_went_online(self._driver_id, self._location, zone_id)

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

        # Notify registry manager that driver went offline
        if self._registry_manager:
            self._registry_manager.driver_went_offline(self._driver_id)

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

        # Notify registry manager of status change
        if self._registry_manager:
            self._registry_manager.driver_status_changed(self._driver_id, self._status)

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

        # Notify registry manager of location update
        if self._registry_manager:
            zone_id = self._determine_zone((lat, lon))
            self._registry_manager.driver_location_updated(self._driver_id, (lat, lon), zone_id)

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

    def submit_rating_for_trip(self, trip: "Trip", rider: "RiderAgent") -> int | None:
        """Submit rating for rider after trip completion."""
        from trip import TripState

        if trip.state != TripState.COMPLETED:
            return None

        rating_value = generate_rating_value(rider.dna.behavior_factor, "behavior_factor")

        if not should_submit_rating(rating_value):
            return None

        rider.update_rating(rating_value)
        self._emit_rating_event(trip.trip_id, rider.rider_id, rating_value)
        return rating_value

    def _emit_rating_event(self, trip_id: str, ratee_id: str, rating_value: int) -> None:
        """Emit rating event to Kafka."""
        if self._kafka_producer is None:
            return

        event = RatingEvent(
            trip_id=trip_id,
            timestamp=datetime.now(UTC).isoformat(),
            rater_type="driver",
            rater_id=self._driver_id,
            ratee_type="rider",
            ratee_id=ratee_id,
            rating=rating_value,
        )

        self._kafka_producer.produce(
            topic="ratings",
            key=trip_id,
            value=event,
        )

    def process_ride_offer(self, offer: dict) -> Generator[simpy.Event, None, bool]:
        """Process ride offer and decide accept/reject."""
        base_delay = self._dna.response_time
        variance = random.uniform(-2.0, 2.0)
        response_delay = max(0, min(14.9, base_delay + variance))

        yield self._env.timeout(response_delay)

        base_rate = self._dna.acceptance_rate
        surge = offer.get("surge_multiplier", 1.0)

        if surge > 1.0:
            modifier = self._dna.surge_acceptance_modifier
            adjusted_rate = base_rate * (1 + (surge - 1) * modifier)
        else:
            adjusted_rate = base_rate

        rider_rating = offer.get("rider_rating", 5.0)
        min_rating = self._dna.min_rider_rating

        if rider_rating < min_rating:
            rating_multiplier = rider_rating / min_rating
            adjusted_rate = adjusted_rate * rating_multiplier

        adjusted_rate = min(1.0, adjusted_rate)

        accept = random.random() < adjusted_rate

        if accept:
            self.accept_trip(offer["trip_id"])
            self.start_pickup()
            return True
        else:
            return False

    def receive_offer(self, offer: dict) -> bool:
        """Decide whether to accept or reject offer based on acceptance rate."""
        base_rate = self._dna.acceptance_rate
        surge = offer.get("surge_multiplier", 1.0)

        if surge > 1.0:
            modifier = self._dna.surge_acceptance_modifier
            adjusted_rate = base_rate * (1 + (surge - 1) * modifier)
        else:
            adjusted_rate = base_rate

        rider_rating = offer.get("rider_rating", 5.0)
        min_rating = self._dna.min_rider_rating

        if rider_rating < min_rating:
            rating_multiplier = rider_rating / min_rating
            adjusted_rate = adjusted_rate * rating_multiplier

        adjusted_rate = min(1.0, adjusted_rate)

        return random.random() < adjusted_rate

    def on_trip_cancelled(self, trip) -> None:
        """Handle trip cancellation notification."""
        if self._status != "offline":
            self.complete_trip()

    def on_trip_started(self, trip) -> None:
        """Handle trip started notification."""
        pass

    def on_trip_completed(self, trip) -> None:
        """Handle trip completion notification."""
        pass

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

    def _calculate_shift_start_time(self) -> float:
        """Calculate shift start time in seconds based on shift preference."""
        shift_windows = {
            "morning": (6, 10),
            "afternoon": (12, 16),
            "evening": (17, 21),
            "night": (22, 26),
            "flexible": (0, 24),
        }

        start_hour, end_hour = shift_windows[self._dna.shift_preference.value]
        base_hour = random.uniform(start_hour, end_hour)
        randomization = random.uniform(-0.5, 0.5)

        shift_start_hour = (base_hour + randomization) % 24
        return shift_start_hour * 3600

    def _get_active_days(self) -> set[int]:
        """Get set of active day numbers (0-6) based on avg_days_per_week."""
        all_days = list(range(7))
        random.shuffle(all_days)
        return set(all_days[: self._dna.avg_days_per_week])

    def _emit_gps_ping(self) -> Generator[simpy.Event]:
        """GPS ping loop that runs while driver is online."""
        import asyncio

        try:
            while self._status in ("online", "busy", "en_route_pickup", "en_route_destination"):
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
        except simpy.Interrupt:
            pass

    def run(self) -> Generator[simpy.Event]:
        """SimPy process managing shift lifecycle and GPS pings."""
        active_days = self._get_active_days()

        while True:
            current_day = int(self._env.now // (24 * 3600)) % 7
            time_of_day = self._env.now % (24 * 3600)

            if current_day in active_days:
                shift_start = self._calculate_shift_start_time()

                if time_of_day < shift_start:
                    yield self._env.timeout(shift_start - time_of_day)

                self.go_online()
                gps_process = self._env.process(self._emit_gps_ping())

                shift_duration = self._dna.avg_hours_per_day * 3600
                yield self._env.timeout(shift_duration)

                while self._active_trip is not None:
                    yield self._env.timeout(30)

                if gps_process.is_alive:
                    gps_process.interrupt()

                self.go_offline()

                time_until_next_day = (24 * 3600) - (self._env.now % (24 * 3600))
                if time_until_next_day > 0:
                    yield self._env.timeout(time_until_next_day)
            else:
                time_until_next_day = (24 * 3600) - time_of_day
                if time_until_next_day > 0:
                    yield self._env.timeout(time_until_next_day)

    def _determine_zone(self, location: tuple[float, float]) -> str | None:
        """Determine the zone ID for a given location.

        Args:
            location: (lat, lon) tuple

        Returns:
            Zone ID if found, None otherwise
        """
        if not self._zone_loader:
            return None
        lat, lon = location
        return self._zone_loader.find_zone_for_location(lat, lon)

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
