"""Driver agent base class for SimPy simulation."""

import json
import logging
import random
import time
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import simpy

from agents.dna import DriverDNA
from agents.dna_generator import SAO_PAULO_BOUNDS
from agents.event_emitter import (
    GPS_PING_INTERVAL_IDLE,
    GPS_PING_INTERVAL_MOVING,
    PROFILE_UPDATE_INTERVAL_SECONDS,
    EventEmitter,
)
from agents.next_action import NextAction, NextActionType
from agents.profile_mutations import mutate_driver_profile
from agents.rating_logic import generate_rating_value, should_submit_rating
from agents.statistics import DriverStatistics
from core.exceptions import PersistenceError
from core.retry import RetryConfig, with_retry_sync
from events.schemas import DriverProfileEvent, GPSPingEvent, RatingEvent
from geo.gps_simulation import GPSSimulator
from kafka.producer import KafkaProducer
from metrics import get_metrics_collector
from redis_client.publisher import RedisPublisher
from utils.async_helpers import run_coroutine_safe

if TYPE_CHECKING:
    from agents.rider_agent import RiderAgent
    from db.repositories.driver_repository import DriverRepository
    from engine import SimulationEngine
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
        simulation_engine: "SimulationEngine | None" = None,
        immediate_online: bool = False,
        puppet: bool = False,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._driver_id = driver_id
        self._dna = dna
        self._env = env
        self._driver_repository = driver_repository
        self._registry_manager = registry_manager
        self._zone_loader = zone_loader
        self._simulation_engine = simulation_engine
        self._immediate_online = immediate_online
        self._is_puppet = puppet
        self._is_ephemeral = False  # Can be set True for non-persisted puppet agents

        # Runtime state
        self._status = "offline"
        # Set initial location from DNA home_location for immediate visibility
        self._location: tuple[float, float] | None = dna.home_location
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0
        self._heading: float = 0.0  # Direction in degrees (0 = North, clockwise)
        self._statistics = DriverStatistics()  # Session-only stats
        self._next_action: NextAction | None = None  # Scheduled next action
        self._persistence_dirty: bool = False  # Tracks failed persistence operations

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.create(driver_id, dna),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_driver_{driver_id}",
                )
            except Exception as e:
                logger.error(f"Failed to persist driver {driver_id} after retries: {e}")
                raise PersistenceError(
                    f"Driver {driver_id} creation failed", {"driver_id": driver_id}
                ) from e

        self._emit_creation_event()

        # For immediate_online drivers, emit initial events for fast UI updates
        # This allows frontend to show driver on map before run() process starts
        if self._immediate_online and self._location:
            self._emit_initial_gps_ping()
            self._emit_initial_status_preview()

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

    @property
    def heading(self) -> float:
        return self._heading

    @property
    def statistics(self) -> DriverStatistics:
        return self._statistics

    @property
    def persistence_dirty(self) -> bool:
        return self._persistence_dirty

    @property
    def next_action(self) -> NextAction | None:
        return self._next_action

    def go_online(self) -> None:
        """Transition from offline to online."""
        previous_status = self._status
        self._status = "online"

        # Set initial random location in São Paulo if not already set
        if self._location is None:
            lat = random.uniform(SAO_PAULO_BOUNDS["lat_min"], SAO_PAULO_BOUNDS["lat_max"])
            lon = random.uniform(SAO_PAULO_BOUNDS["lon_min"], SAO_PAULO_BOUNDS["lon_max"])
            self._location = (lat, lon)

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_status(self._driver_id, self._status),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_status_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist status for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

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
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_status(self._driver_id, self._status),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_status_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist status for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

        # Notify registry manager that driver went offline
        if self._registry_manager:
            self._registry_manager.driver_went_offline(self._driver_id)

        self._emit_status_event(previous_status, self._status, "go_offline")

    def accept_trip(self, trip_id: str) -> None:
        """Accept a trip offer, transition directly to en_route_pickup."""
        previous_status = self._status
        self._status = "en_route_pickup"
        self._active_trip = trip_id

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: (  # type: ignore[misc]
                        repo.update_status(self._driver_id, self._status),
                        repo.update_active_trip(self._driver_id, trip_id),
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_trip_acceptance_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist trip acceptance for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

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
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_status(self._driver_id, self._status),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_status_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist status for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

        # Notify registry manager of status change
        if self._registry_manager:
            self._registry_manager.driver_status_changed(self._driver_id, self._status)

        self._emit_status_event(previous_status, self._status, "start_pickup")

    def start_trip(self) -> None:
        """Start the trip after rider pickup."""
        previous_status = self._status
        self._status = "en_route_destination"

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_status(self._driver_id, self._status),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_status_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist status for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

        # Notify registry manager of status change
        if self._registry_manager:
            self._registry_manager.driver_status_changed(self._driver_id, self._status)

        self._emit_status_event(previous_status, self._status, "start_trip")

    def complete_trip(self) -> None:
        """Complete the trip and return to online."""
        previous_status = self._status
        self._status = "online"
        self._active_trip = None

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: (  # type: ignore[misc]
                        repo.update_status(self._driver_id, self._status),
                        repo.update_active_trip(self._driver_id, None),
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_trip_completion_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist trip completion for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

        # Notify registry manager of status change
        if self._registry_manager:
            self._registry_manager.driver_status_changed(self._driver_id, self._status)

        self._emit_status_event(previous_status, self._status, "complete_trip")

    def update_location(self, lat: float, lon: float, heading: float | None = None) -> None:
        """Update current location and optionally heading.

        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate
            heading: Optional heading in degrees. If provided, uses this value.
                     If None, calculates heading from previous location.
        """
        if heading is not None:
            self._heading = heading
        elif self._location is not None:
            gps = GPSSimulator(noise_meters=0)
            calculated = gps.calculate_heading(self._location, (lat, lon))
            # Only update heading if position actually changed (avoid 0 from same-point calculation)
            if self._location != (lat, lon):
                self._heading = calculated

        self._location = (lat, lon)

        if self._driver_repository:
            try:
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_location(self._driver_id, (lat, lon)),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_location_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist location for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

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
                repo = self._driver_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_rating(  # type: ignore[misc]
                        self._driver_id, self._current_rating, self._rating_count
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_driver_rating_{self._driver_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist rating for driver {self._driver_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def submit_rating_for_trip(self, trip: "Trip", rider: "RiderAgent") -> int | None:
        """Submit rating for rider after trip completion."""
        from trip import TripState

        if trip.state != TripState.COMPLETED:
            return None

        rating_value = generate_rating_value(rider.dna.behavior_factor, "behavior_factor")

        if not should_submit_rating(rating_value):
            return None

        rider.update_rating(rating_value)
        self._statistics.record_rating_given(rating_value)
        self._emit_rating_event(
            trip_id=trip.trip_id,
            ratee_id=rider.rider_id,
            rating_value=rating_value,
            current_rating=rider.current_rating,
            rating_count=rider.rating_count,
        )
        return rating_value

    def _emit_rating_event(
        self,
        trip_id: str,
        ratee_id: str,
        rating_value: int,
        current_rating: float,
        rating_count: int,
    ) -> None:
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
            current_rating=current_rating,
            rating_count=rating_count,
        )

        self._kafka_producer.produce(
            topic="ratings",
            key=trip_id,
            value=event,
        )

    def process_ride_offer(self, offer: dict[str, Any]) -> Generator[simpy.Event, None, bool]:
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

    def receive_offer(self, offer: dict[str, Any]) -> bool:
        """Decide whether to accept or reject offer based on acceptance rate.

        If accepted, updates driver status to en_route_pickup via accept_trip().
        """
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

        if random.random() < adjusted_rate:
            self.accept_trip(offer["trip_id"])
            return True
        return False

    def on_trip_cancelled(self, trip: "Trip") -> None:
        """Handle trip cancellation notification."""
        if self._status != "offline":
            self.complete_trip()

    def on_trip_started(self, trip: "Trip") -> None:
        """Handle trip started notification."""
        pass

    def on_trip_completed(self, trip: "Trip") -> None:
        """Handle trip completion notification."""
        pass

    def _emit_creation_event(self) -> None:
        """Emit driver.created event on initialization."""
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

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=event,
                kafka_topic="driver_profiles",
                partition_key=self._driver_id,
                redis_channel="driver-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

    def _emit_update_event(self) -> None:
        """Emit driver.updated event with mutated profile fields."""
        changes = mutate_driver_profile(self._dna)
        if not changes:
            return

        event = DriverProfileEvent(
            event_type="driver.updated",
            driver_id=self._driver_id,
            timestamp=datetime.now(UTC).isoformat(),
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=changes.get("email", self._dna.email),
            phone=changes.get("phone", self._dna.phone),
            home_location=self._dna.home_location,
            preferred_zones=self._dna.preferred_zones,
            shift_preference=changes.get("shift_preference", self._dna.shift_preference.value),
            vehicle_make=changes.get("vehicle_make", self._dna.vehicle_make),
            vehicle_model=changes.get("vehicle_model", self._dna.vehicle_model),
            vehicle_year=changes.get("vehicle_year", self._dna.vehicle_year),
            license_plate=changes.get("license_plate", self._dna.license_plate),
        )

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=event,
                kafka_topic="driver_profiles",
                partition_key=self._driver_id,
                redis_channel="driver-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

    def _emit_initial_gps_ping(self) -> None:
        """Emit a single GPS ping immediately on creation for map visibility."""
        if self._location is None:
            return

        event = GPSPingEvent(
            entity_type="driver",
            entity_id=self._driver_id,
            timestamp=datetime.now(UTC).isoformat(),
            location=self._location,
            heading=self._heading,
            speed=0.0,
            accuracy=5.0,
            trip_id=None,
        )

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=event,
                kafka_topic="gps_pings",
                partition_key=self._driver_id,
                redis_channel="driver-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

    def _emit_initial_status_preview(self) -> None:
        """Emit status event immediately on creation for frontend visibility.

        This is a 'preview' showing the driver as online before run() starts.
        The actual go_online() in run() will update registries and emit another event.
        """

        event = {
            "event_id": str(uuid4()),
            "driver_id": self._driver_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_status": "offline",
            "new_status": "online",
            "trigger": "creation_preview",
            "location": list(self._location) if self._location else [0.0, 0.0],
        }

        # Record event for metrics
        collector = get_metrics_collector()
        collector.record_event("driver_status")

        # Emit to Kafka with latency tracking
        if self._kafka_producer is not None:
            start_time = time.perf_counter()
            self._kafka_producer.produce(
                topic="driver_status",
                key=self._driver_id,
                value=json.dumps(event),
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("kafka", latency_ms)

        # NOTE: Direct Redis publishing disabled - using Kafka → Stream Processor → Redis path
        # See stream-processor service for event routing

    def _emit_status_event(self, previous_status: str, new_status: str, trigger: str) -> None:
        """Emit driver status event to Kafka and Redis."""

        event = {
            "event_id": str(uuid4()),
            "driver_id": self._driver_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_status": previous_status,
            "new_status": new_status,
            "trigger": trigger,
            "location": list(self._location) if self._location else [0.0, 0.0],
        }

        # Record event for metrics
        collector = get_metrics_collector()
        collector.record_event("driver_status")

        # Emit to Kafka with latency tracking
        if self._kafka_producer is not None:
            start_time = time.perf_counter()
            self._kafka_producer.produce(
                topic="driver_status",
                key=self._driver_id,
                value=json.dumps(event),
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("kafka", latency_ms)

        # NOTE: Direct Redis publishing disabled - testing Kafka → Stream Processor → Redis path
        # If this works, remove this commented block entirely
        # if self._redis_publisher is not None:
        #     redis_message = {
        #         "driver_id": self._driver_id,
        #         "status": new_status,
        #         "location": list(self._location) if self._location else [0.0, 0.0],
        #         "rating": self._current_rating,
        #         "heading": self._heading,
        #     }
        #     try:
        #         loop = asyncio.get_event_loop()
        #         if loop.is_running():
        #             asyncio.create_task(
        #                 self._redis_publisher.publish(
        #                     channel="driver-updates",
        #                     message=redis_message,
        #                 )
        #             )
        #         else:
        #             loop.run_until_complete(
        #                 self._redis_publisher.publish(
        #                     channel="driver-updates",
        #                     message=redis_message,
        #                 )
        #             )
        #     except RuntimeError:
        #         asyncio.run(
        #             self._redis_publisher.publish(
        #                 channel="driver-updates",
        #                 message=redis_message,
        #             )
        #         )

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

    def _get_gps_interval(self) -> int:
        """Return GPS ping interval based on current status.

        Moving drivers (en_route_pickup, en_route_destination) ping more frequently
        to support accurate arrival detection and smooth visualization.
        Idle drivers (online) ping less frequently to reduce load.
        """
        if self._status in ("en_route_pickup", "en_route_destination"):
            return GPS_PING_INTERVAL_MOVING
        else:  # online
            return GPS_PING_INTERVAL_IDLE

    def _emit_gps_ping(self) -> Generator[simpy.Event]:
        """GPS ping loop that runs while driver is online."""
        try:
            while self._status in (
                "online",
                "en_route_pickup",
                "en_route_destination",
            ):
                if self._location:
                    event = GPSPingEvent(
                        entity_type="driver",
                        entity_id=self._driver_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        location=self._location,
                        heading=self._heading,
                        speed=random.uniform(20, 60),
                        accuracy=5.0,
                        trip_id=self._active_trip,
                    )

                    main_loop = None
                    if self._simulation_engine:
                        main_loop = self._simulation_engine.get_event_loop()
                    run_coroutine_safe(
                        self._emit_event(
                            event=event,
                            kafka_topic="gps_pings",
                            partition_key=self._driver_id,
                            redis_channel="driver-updates",
                        ),
                        main_loop,
                        fallback_sync=True,
                    )

                yield self._env.timeout(self._get_gps_interval())
        except simpy.Interrupt:
            pass

    def _profile_update_loop(self) -> Generator[simpy.Event]:
        """Periodic profile update loop for SCD Type 2 events.

        Emits driver.updated events at intervals with variance.
        Puppets do not emit profile updates.
        """
        try:
            while True:
                # Add variance (0.5x to 1.5x) to prevent synchronized updates
                variance = random.uniform(0.5, 1.5)
                yield self._env.timeout(PROFILE_UPDATE_INTERVAL_SECONDS * variance)
                if not self._is_puppet:
                    self._emit_update_event()
        except simpy.Interrupt:
            pass

    def run(self) -> Generator[simpy.Event]:
        """SimPy process managing shift lifecycle and GPS pings."""
        # Puppet mode: only emit GPS pings, no autonomous actions
        if self._is_puppet:
            gps_process = None
            while True:
                # Start/restart GPS process when not offline
                if self._status != "offline" and (gps_process is None or not gps_process.is_alive):
                    gps_process = self._env.process(self._emit_gps_ping())
                yield self._env.timeout(self._get_gps_interval())
            return

        # Start profile update background process (non-puppet only)
        # This runs throughout the agent's lifetime for SCD Type 2 tracking
        self._env.process(self._profile_update_loop())

        # Immediate mode: go online right away, then follow shift lifecycle
        if self._immediate_online:
            while True:
                self.go_online()
                gps_process = self._env.process(self._emit_gps_ping())

                # Schedule shift end based on DNA
                shift_duration = self._dna.avg_hours_per_day * 3600
                self._next_action = NextAction(
                    action_type=NextActionType.GO_OFFLINE,
                    scheduled_at=self._env.now + shift_duration,
                    description="Shift ends",
                )
                yield self._env.timeout(shift_duration)

                # Wait for active trip to complete before going offline
                while self._active_trip is not None:
                    self._next_action = NextAction(
                        action_type=NextActionType.GO_OFFLINE,
                        scheduled_at=self._env.now + 30,
                        description="Finishing trip, then going offline",
                    )
                    yield self._env.timeout(30)

                if gps_process.is_alive:
                    gps_process.interrupt()

                self._next_action = None
                self.go_offline()

                # Rest period before next shift (use avg_hours as proxy, min 4 hours)
                rest_duration = max(4 * 3600, (24 - self._dna.avg_hours_per_day) * 3600)
                self._next_action = NextAction(
                    action_type=NextActionType.GO_ONLINE,
                    scheduled_at=self._env.now + rest_duration,
                    description="Next shift starts",
                )
                yield self._env.timeout(rest_duration)

        # Normal shift-based mode
        active_days = self._get_active_days()

        while True:
            current_day = int(self._env.now // (24 * 3600)) % 7
            time_of_day = self._env.now % (24 * 3600)

            if current_day in active_days:
                shift_start = self._calculate_shift_start_time()

                if time_of_day < shift_start:
                    # Track: waiting to go online for shift start
                    self._next_action = NextAction(
                        action_type=NextActionType.GO_ONLINE,
                        scheduled_at=self._env.now + (shift_start - time_of_day),
                        description="Shift starts",
                    )
                    yield self._env.timeout(shift_start - time_of_day)

                self._next_action = None  # Clear while transitioning
                self.go_online()
                gps_process = self._env.process(self._emit_gps_ping())

                shift_duration = self._dna.avg_hours_per_day * 3600
                # Track: waiting to go offline at shift end
                self._next_action = NextAction(
                    action_type=NextActionType.GO_OFFLINE,
                    scheduled_at=self._env.now + shift_duration,
                    description="Shift ends",
                )
                yield self._env.timeout(shift_duration)

                # Waiting for active trip to complete before going offline
                while self._active_trip is not None:
                    self._next_action = NextAction(
                        action_type=NextActionType.GO_OFFLINE,
                        scheduled_at=self._env.now + 30,
                        description="Finishing trip, then going offline",
                    )
                    yield self._env.timeout(30)

                if gps_process.is_alive:
                    gps_process.interrupt()

                self._next_action = None  # Clear while transitioning
                self.go_offline()

                time_until_next_day = (24 * 3600) - (self._env.now % (24 * 3600))
                if time_until_next_day > 0:
                    # Track: waiting for next day to start shift
                    self._next_action = NextAction(
                        action_type=NextActionType.GO_ONLINE,
                        scheduled_at=self._env.now + time_until_next_day,
                        description="Next shift starts tomorrow",
                    )
                    yield self._env.timeout(time_until_next_day)
            else:
                time_until_next_day = (24 * 3600) - time_of_day
                if time_until_next_day > 0:
                    # Track: not active today, waiting for next day
                    self._next_action = NextAction(
                        action_type=NextActionType.GO_ONLINE,
                        scheduled_at=self._env.now + time_until_next_day,
                        description="Not active today, waiting for next day",
                    )
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

    @property
    def is_ephemeral(self) -> bool:
        """Check if this is an ephemeral (non-persisted) agent."""
        return getattr(self, "_is_ephemeral", False)

    @property
    def is_puppet(self) -> bool:
        """Check if this is a puppet (manually controlled) agent."""
        return getattr(self, "_is_puppet", False)

    def get_state(self, zone_loader: "ZoneLoader | None" = None) -> dict[str, Any]:
        """Extract full agent state for API inspection.

        Args:
            zone_loader: Optional zone loader to determine current zone

        Returns:
            Dictionary containing driver state
        """
        zone_id = None
        loader = zone_loader or self._zone_loader
        if loader and self._location:
            zone_id = loader.find_zone_for_location(self._location[0], self._location[1])

        return {
            "driver_id": self._driver_id,
            "status": self._status,
            "location": self._location,
            "current_rating": self._current_rating,
            "rating_count": self._rating_count,
            "active_trip": self._active_trip,
            "zone_id": zone_id,
            "is_ephemeral": self.is_ephemeral,
            "is_puppet": self.is_puppet,
        }

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
        agent._statistics = DriverStatistics()  # Session-only, not persisted

        return agent
