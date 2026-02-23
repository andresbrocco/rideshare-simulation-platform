"""Driver agent base class for SimPy simulation."""

import logging
import random
import time
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
from events.factory import EventFactory
from events.schemas import (
    DriverProfileEvent,
    DriverStatusEvent,
    GPSPingEvent,
    RatingEvent,
)
from geo.distance import haversine_distance_km
from geo.gps_simulation import GPSSimulator
from kafka.producer import KafkaProducer
from metrics import get_metrics_collector
from metrics.prometheus_exporter import observe_latency
from redis_client.publisher import RedisPublisher
from trips.drive_simulation import simulate_drive_along_route

if TYPE_CHECKING:
    from agents.rider_agent import RiderAgent
    from db.repositories.driver_repository import DriverRepository
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient
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
        osrm_client: "OSRMClient | None" = None,
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
        self._osrm_client = osrm_client

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
        self._last_emitted_location: tuple[float, float] | None = None
        self._route_progress_index: int | None = None
        self._pickup_route_progress_index: int | None = None
        self._reposition_process: simpy.Process | None = None

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

        # Pre-compute timestamp once for the creation + initial events batch
        ts = self._format_timestamp()
        self._emit_creation_event(ts)

        # For immediate_online drivers, emit initial events for fast UI updates
        # This allows frontend to show driver on map before run() process starts
        if self._immediate_online and self._location:
            self._emit_initial_gps_ping(ts)
            self._emit_initial_status_preview(ts)

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
        self._status = "available"

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
        # Interrupt any active repositioning
        if self._reposition_process is not None and self._reposition_process.is_alive:
            self._reposition_process.interrupt()
            self._reposition_process = None

        # Teleport to home location (simulating "closed app, drove home")
        self.update_location(*self._dna.home_location)

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

        self._last_emitted_location = None
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
        self._status = "on_trip"

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
        self._status = "available"
        self._active_trip = None
        self._route_progress_index = None
        self._pickup_route_progress_index = None

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

    def update_route_progress(
        self,
        route_progress_index: int | None = None,
        pickup_route_progress_index: int | None = None,
    ) -> None:
        self._route_progress_index = route_progress_index
        self._pickup_route_progress_index = pickup_route_progress_index

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
        elif self._location is not None and self._location != (lat, lon):
            self._heading = GPSSimulator.calculate_heading(self._location, (lat, lon))

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

    def _format_timestamp(self) -> str:
        """Format current timestamp using simulated time if available."""
        if self._simulation_engine:
            result = self._simulation_engine.time_manager.format_timestamp()
            if isinstance(result, str):
                return result
        return datetime.now(UTC).isoformat()

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

        event = EventFactory.create(
            RatingEvent,
            correlation_id=trip_id,
            trip_id=trip_id,
            timestamp=self._format_timestamp(),
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
            if self._reposition_process is not None and self._reposition_process.is_alive:
                self._reposition_process.interrupt()
                self._reposition_process = None
            self.accept_trip(offer["trip_id"])
            return True
        return False

    @staticmethod
    def _calculate_reposition_target(
        current: tuple[float, float],
        home: tuple[float, float],
        distance_km: float,
    ) -> tuple[float, float]:
        """Calculate a GPS point 10 km from home along the current->home line.

        If the driver is 50 km from home, the target is 40 km from the driver
        (10 km from home) along the straight line toward home.
        """
        ratio = (distance_km - 10.0) / distance_km
        target_lat = current[0] + ratio * (home[0] - current[0])
        target_lon = current[1] + ratio * (home[1] - current[1])
        return (target_lat, target_lon)

    def _drive_toward_home(self) -> Generator[simpy.Event]:
        """SimPy process: drive toward home if far away after trip completion."""
        try:
            if self._location is None:
                return

            home = self._dna.home_location
            distance = haversine_distance_km(
                self._location[0],
                self._location[1],
                home[0],
                home[1],
            )

            if distance <= 10.0:
                return  # Close enough, no repositioning needed

            if self._osrm_client is None:
                return

            target = self._calculate_reposition_target(self._location, home, distance)

            # Enter repositioning status (still matchable for trips)
            previous_status = self._status
            self._status = "driving_closer_to_home"
            if self._registry_manager:
                self._registry_manager.driver_status_changed(self._driver_id, self._status)
            self._emit_status_event(previous_status, self._status, "start_repositioning")

            route = self._osrm_client.get_route_sync(self._location, target)

            yield from simulate_drive_along_route(
                env=self._env,
                driver=self,
                geometry=route.geometry,
                duration=route.duration_seconds,
                destination=target,
                check_proximity=True,
                proximity_threshold_m=100.0,
            )

            # Return to available after repositioning
            previous_status = self._status
            self._status = "available"
            if self._registry_manager:
                self._registry_manager.driver_status_changed(self._driver_id, self._status)
            self._emit_status_event(previous_status, self._status, "end_repositioning")

        except simpy.Interrupt:
            logger.debug(f"Driver {self._driver_id}: Repositioning interrupted by trip offer")
        except Exception as e:
            logger.warning(f"Driver {self._driver_id}: Repositioning failed: {e}")
            # Fall back to available on failure
            if self._status == "driving_closer_to_home":
                previous_status = self._status
                self._status = "available"
                if self._registry_manager:
                    self._registry_manager.driver_status_changed(self._driver_id, self._status)
                self._emit_status_event(previous_status, self._status, "repositioning_failed")

    def on_trip_cancelled(self, trip: "Trip") -> None:
        """Handle trip cancellation notification."""
        if self._status != "offline":
            self.complete_trip()

    def on_trip_started(self, trip: "Trip") -> None:
        """Handle trip started notification."""
        pass

    def on_trip_completed(self, trip: "Trip") -> None:
        """Handle trip completion — start repositioning toward home if far away."""
        if self._status == "available" and self._osrm_client:
            if self._reposition_process is not None and self._reposition_process.is_alive:
                self._reposition_process.interrupt()
            self._reposition_process = self._env.process(self._drive_toward_home())

    def _emit_creation_event(self, timestamp: str | None = None) -> None:
        """Emit driver.created event on initialization."""
        ts = timestamp or self._format_timestamp()
        event = EventFactory.create(
            DriverProfileEvent,
            correlation_id=self._driver_id,
            event_type="driver.created",
            driver_id=self._driver_id,
            timestamp=ts,
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=self._dna.email,
            phone=self._dna.phone,
            home_location=self._dna.home_location,
            shift_preference=self._dna.shift_preference.value,
            vehicle_make=self._dna.vehicle_make,
            vehicle_model=self._dna.vehicle_model,
            vehicle_year=self._dna.vehicle_year,
            license_plate=self._dna.license_plate,
        )

        self._emit_event(
            event=event,
            kafka_topic="driver_profiles",
            partition_key=self._driver_id,
            redis_channel="driver-updates",
        )

    def _emit_update_event(self) -> None:
        """Emit driver.updated event with mutated profile fields."""
        changes = mutate_driver_profile(self._dna)
        if not changes:
            return

        event = EventFactory.create(
            DriverProfileEvent,
            correlation_id=self._driver_id,
            event_type="driver.updated",
            driver_id=self._driver_id,
            timestamp=self._format_timestamp(),
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=changes.get("email", self._dna.email),
            phone=changes.get("phone", self._dna.phone),
            home_location=self._dna.home_location,
            shift_preference=changes.get("shift_preference", self._dna.shift_preference.value),
            vehicle_make=changes.get("vehicle_make", self._dna.vehicle_make),
            vehicle_model=changes.get("vehicle_model", self._dna.vehicle_model),
            vehicle_year=changes.get("vehicle_year", self._dna.vehicle_year),
            license_plate=changes.get("license_plate", self._dna.license_plate),
        )

        self._emit_event(
            event=event,
            kafka_topic="driver_profiles",
            partition_key=self._driver_id,
            redis_channel="driver-updates",
        )

    def _emit_initial_gps_ping(self, timestamp: str | None = None) -> None:
        """Emit a single GPS ping immediately on creation for map visibility."""
        if self._location is None:
            return

        ts = timestamp or self._format_timestamp()
        event = EventFactory.create(
            GPSPingEvent,
            correlation_id=self._driver_id,
            entity_type="driver",
            entity_id=self._driver_id,
            timestamp=ts,
            location=self._location,
            heading=self._heading,
            speed=0.0,
            accuracy=5.0,
            trip_id=None,
        )

        self._emit_event(
            event=event,
            kafka_topic="gps_pings",
            partition_key=self._driver_id,
            redis_channel="driver-updates",
        )

    def _emit_initial_status_preview(self, timestamp: str | None = None) -> None:
        """Emit status event immediately on creation for frontend visibility.

        This is a 'preview' showing the driver as online before run() starts.
        The actual go_online() in run() will update registries and emit another event.
        """
        ts = timestamp or self._format_timestamp()
        event = EventFactory.create(
            DriverStatusEvent,
            correlation_id=self._driver_id,
            driver_id=self._driver_id,
            timestamp=ts,
            previous_status="offline",
            new_status="available",
            trigger="creation_preview",
            location=self._location if self._location else (0.0, 0.0),
        )

        # Record event for metrics
        collector = get_metrics_collector()
        collector.record_event("driver_status")

        # Emit to Kafka with latency tracking
        if self._kafka_producer is not None:
            start_time = time.perf_counter()
            self._kafka_producer.produce(
                topic="driver_status",
                key=self._driver_id,
                value=event,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("kafka", latency_ms)
            observe_latency("kafka", latency_ms)

        # NOTE: Direct Redis publishing disabled - using Kafka → Stream Processor → Redis path
        # See stream-processor service for event routing

    def _emit_status_event(self, previous_status: str, new_status: str, trigger: str) -> None:
        """Emit driver status event to Kafka and Redis."""

        event = EventFactory.create(
            DriverStatusEvent,
            correlation_id=self._driver_id,
            driver_id=self._driver_id,
            timestamp=self._format_timestamp(),
            previous_status=previous_status,
            new_status=new_status,
            trigger=trigger,
            location=self._location if self._location else (0.0, 0.0),
        )

        # Record event for metrics
        collector = get_metrics_collector()
        collector.record_event("driver_status")

        # Emit to Kafka with latency tracking
        if self._kafka_producer is not None:
            start_time = time.perf_counter()
            self._kafka_producer.produce(
                topic="driver_status",
                key=self._driver_id,
                value=event,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("kafka", latency_ms)
            observe_latency("kafka", latency_ms)

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

        Moving drivers (en_route_pickup, on_trip) ping more frequently
        to support accurate arrival detection and smooth visualization.
        Idle drivers (available) ping less frequently to reduce load.
        """
        if self._status in ("en_route_pickup", "on_trip", "driving_closer_to_home"):
            return GPS_PING_INTERVAL_MOVING
        else:  # available
            return GPS_PING_INTERVAL_IDLE

    def _emit_gps_ping(self) -> Generator[simpy.Event]:
        """GPS ping loop that runs while driver is online."""
        try:
            while self._status in (
                "available",
                "en_route_pickup",
                "on_trip",
                "driving_closer_to_home",
            ):
                if self._location and self._location != self._last_emitted_location:
                    # Use trip_id as correlation if in trip, otherwise driver_id
                    correlation = self._active_trip or self._driver_id
                    event = EventFactory.create(
                        GPSPingEvent,
                        correlation_id=correlation,
                        entity_type="driver",
                        entity_id=self._driver_id,
                        timestamp=self._format_timestamp(),
                        location=self._location,
                        heading=self._heading,
                        speed=random.uniform(20, 60),
                        accuracy=5.0,
                        trip_id=self._active_trip,
                        route_progress_index=self._route_progress_index,
                        pickup_route_progress_index=self._pickup_route_progress_index,
                    )

                    self._emit_event(
                        event=event,
                        kafka_topic="gps_pings",
                        partition_key=self._driver_id,
                        redis_channel="driver-updates",
                    )
                    self._last_emitted_location = self._location

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
