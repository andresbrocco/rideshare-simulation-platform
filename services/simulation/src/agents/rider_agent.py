"""Rider agent base class for SimPy simulation."""

import asyncio
import logging
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import simpy

from agents.dna import RiderDNA
from agents.event_emitter import (
    GPS_PING_INTERVAL_MOVING,
    PROFILE_UPDATE_INTERVAL_SECONDS,
    EventEmitter,
)
from agents.next_action import NextAction, NextActionType
from agents.profile_mutations import mutate_rider_profile
from agents.rating_logic import generate_rating_value, should_submit_rating
from agents.statistics import RiderStatistics
from core.exceptions import PersistenceError
from core.retry import RetryConfig, with_retry_sync
from events.factory import EventFactory
from events.schemas import GPSPingEvent, RatingEvent, RiderProfileEvent, TripEvent
from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher
from utils.async_helpers import run_coroutine_safe

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from db.repositories.rider_repository import RiderRepository
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient
    from geo.zones import ZoneLoader
    from matching.surge_pricing import SurgePricingCalculator
    from trip import Trip

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
        simulation_engine: "SimulationEngine | None" = None,
        zone_loader: "ZoneLoader | None" = None,
        osrm_client: "OSRMClient | None" = None,
        surge_calculator: "SurgePricingCalculator | None" = None,
        immediate_first_trip: bool = False,
        puppet: bool = False,
    ):
        EventEmitter.__init__(self, kafka_producer, redis_publisher)

        self._rider_id = rider_id
        self._dna = dna
        self._env = env
        self._rider_repository = rider_repository
        self._simulation_engine = simulation_engine
        self._zone_loader = zone_loader
        self._osrm_client = osrm_client
        self._surge_calculator = surge_calculator
        self._immediate_first_trip = immediate_first_trip
        self._first_trip_done = False
        self._is_puppet = puppet
        self._is_ephemeral = False  # Can be set True for non-persisted puppet agents

        # Runtime state
        self._status = "offline"
        # Set initial location from DNA home_location for immediate visibility
        self._location: tuple[float, float] | None = dna.home_location
        self._active_trip: str | None = None
        self._current_rating = 5.0
        self._rating_count = 0
        self._statistics = RiderStatistics()  # Session-only stats
        self._next_action: NextAction | None = None  # Scheduled next action
        self._persistence_dirty: bool = False  # Tracks failed persistence operations

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: repo.create(rider_id, dna),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_rider_{rider_id}",
                )
            except Exception as e:
                logger.error(f"Failed to persist rider {rider_id} after retries: {e}")
                raise PersistenceError(
                    f"Rider {rider_id} creation failed", {"rider_id": rider_id}
                ) from e

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

    @property
    def statistics(self) -> RiderStatistics:
        return self._statistics

    @property
    def persistence_dirty(self) -> bool:
        return self._persistence_dirty

    @property
    def next_action(self) -> NextAction | None:
        return self._next_action

    def request_trip(self, trip_id: str) -> None:
        """Transition from offline to waiting, set active trip."""
        self._status = "waiting"
        self._active_trip = trip_id
        self._statistics.record_trip_requested()

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: (  # type: ignore[misc]
                        repo.update_status(self._rider_id, self._status),
                        repo.update_active_trip(self._rider_id, trip_id),
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_trip_request_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist trip request for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def start_trip(self) -> None:
        """Transition from waiting to in_trip."""
        self._status = "in_trip"

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_status(self._rider_id, self._status),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_rider_status_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist status for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def complete_trip(self) -> None:
        """Transition from in_trip to offline, clear active trip."""
        self._status = "offline"
        self._active_trip = None

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: (  # type: ignore[misc]
                        repo.update_status(self._rider_id, self._status),
                        repo.update_active_trip(self._rider_id, None),
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_trip_completion_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist trip completion for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def cancel_trip(self) -> None:
        """Transition from waiting to offline, clear active trip."""
        self._status = "offline"
        self._active_trip = None

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: (  # type: ignore[misc]
                        repo.update_status(self._rider_id, self._status),
                        repo.update_active_trip(self._rider_id, None),
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"persist_trip_cancellation_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist trip cancellation for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def update_location(self, lat: float, lon: float) -> None:
        """Update current location."""
        self._location = (lat, lon)

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_location(self._rider_id, (lat, lon)),  # type: ignore[misc]
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_rider_location_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist location for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def update_rating(self, new_rating: int) -> None:
        """Update rolling average rating."""
        self._current_rating = (self._current_rating * self._rating_count + new_rating) / (
            self._rating_count + 1
        )
        self._rating_count += 1

        if self._rider_repository:
            try:
                repo = self._rider_repository
                with_retry_sync(
                    lambda repo=repo: repo.update_rating(  # type: ignore[misc]
                        self._rider_id, self._current_rating, self._rating_count
                    ),
                    config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                    operation_name=f"update_rider_rating_{self._rider_id}",
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist rating for rider {self._rider_id} after retries: {e}"
                )
                self._persistence_dirty = True

    def submit_rating_for_trip(self, trip: "Trip", driver: "DriverAgent") -> int | None:
        """Submit rating for driver after trip completion."""
        from trip import TripState

        if trip.state != TripState.COMPLETED:
            return None

        rating_value = generate_rating_value(driver.dna.service_quality, "service_quality")

        if not should_submit_rating(rating_value):
            return None

        driver.update_rating(rating_value)
        self._statistics.record_rating_given(rating_value)
        self._emit_rating_event(
            trip_id=trip.trip_id,
            ratee_id=driver.driver_id,
            rating_value=rating_value,
            current_rating=driver.current_rating,
            rating_count=driver.rating_count,
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

        event = EventFactory.create(
            RatingEvent,
            correlation_id=trip_id,
            trip_id=trip_id,
            timestamp=datetime.now(UTC).isoformat(),
            rater_type="rider",
            rater_id=self._rider_id,
            ratee_type="driver",
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
        """Generate random location within a valid São Paulo zone."""
        from agents.zone_validator import get_random_location_in_zones

        return get_random_location_in_zones()

    def on_match_found(self, trip: "Trip", driver_id: str) -> None:
        """Handle match found notification."""
        self.request_trip(trip.trip_id)

    def on_no_drivers_available(self, trip_id: str) -> None:
        """Handle no drivers available notification."""
        pass

    def on_trip_cancelled(self, trip: "Trip") -> None:
        """Handle trip cancellation notification."""
        if self._status != "offline":
            self.cancel_trip()

    def on_driver_en_route(self, trip: "Trip") -> None:
        """Handle driver en route notification.

        Transition from waiting to in_trip so the patience timeout
        doesn't cancel the trip while the driver is on the way.
        """
        if self._status == "waiting":
            self._status = "in_trip"

            if self._rider_repository:
                try:
                    repo = self._rider_repository
                    with_retry_sync(
                        lambda repo=repo: repo.update_status(self._rider_id, self._status),  # type: ignore[misc]
                        config=RetryConfig(max_attempts=3, retryable_exceptions=(Exception,)),
                        operation_name=f"update_rider_status_{self._rider_id}",
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to persist status for rider {self._rider_id} after retries: {e}"
                    )
                    self._persistence_dirty = True

    def on_driver_arrived(self, trip: "Trip") -> None:
        """Handle driver arrival notification."""
        pass

    def on_trip_started(self, trip: "Trip") -> None:
        """Handle trip started notification."""
        pass

    def on_trip_completed(self, trip: "Trip") -> None:
        """Handle trip completion notification."""
        pass

    def _emit_creation_event(self) -> None:
        """Emit rider.created event on initialization."""
        event = EventFactory.create(
            RiderProfileEvent,
            correlation_id=self._rider_id,
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

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=event,
                kafka_topic="rider_profiles",
                partition_key=self._rider_id,
                redis_channel="rider-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

        # NOTE: Direct Redis publishing disabled - using Kafka → Stream Processor → Redis path
        # See stream-processor service for event routing

    def _emit_update_event(self) -> None:
        """Emit rider.updated event with mutated profile fields."""
        changes = mutate_rider_profile(self._dna)
        if not changes:
            return

        event = EventFactory.create(
            RiderProfileEvent,
            correlation_id=self._rider_id,
            event_type="rider.updated",
            rider_id=self._rider_id,
            timestamp=datetime.now(UTC).isoformat(),
            first_name=self._dna.first_name,
            last_name=self._dna.last_name,
            email=changes.get("email", self._dna.email),
            phone=changes.get("phone", self._dna.phone),
            home_location=self._dna.home_location,
            payment_method_type=changes.get("payment_method_type", self._dna.payment_method_type),
            payment_method_masked=changes.get(
                "payment_method_masked", self._dna.payment_method_masked
            ),
            behavior_factor=self._dna.behavior_factor,
        )

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=event,
                kafka_topic="rider_profiles",
                partition_key=self._rider_id,
                redis_channel="rider-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

    def _profile_update_loop(self) -> Generator[simpy.Event]:
        """Periodic profile update loop for SCD Type 2 events.

        Emits rider.updated events at intervals with variance.
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

    def _emit_puppet_gps_ping(self) -> None:
        """Emit a single GPS ping for puppet rider."""
        if self._location is None:
            return

        # Use trip_id as correlation if in trip, otherwise rider_id
        correlation = self._active_trip or self._rider_id
        gps_event = EventFactory.create(
            GPSPingEvent,
            correlation_id=correlation,
            entity_type="rider",
            entity_id=self._rider_id,
            timestamp=datetime.now(UTC).isoformat(),
            location=self._location,
            heading=None,
            speed=None,
            accuracy=5.0,
            trip_id=self._active_trip,
        )

        main_loop = None
        if self._simulation_engine:
            main_loop = self._simulation_engine.get_event_loop()
        run_coroutine_safe(
            self._emit_event(
                event=gps_event,
                kafka_topic="gps_pings",
                partition_key=self._rider_id,
                redis_channel="rider-updates",
            ),
            main_loop,
            fallback_sync=True,
        )

    def run(self) -> Generator[simpy.Event]:
        """SimPy process entry point with request lifecycle."""
        import uuid

        # Puppet mode: only emit GPS pings, no autonomous actions
        if self._is_puppet:
            while True:
                self._emit_puppet_gps_ping()
                yield self._env.timeout(GPS_PING_INTERVAL_MOVING)
            return

        # Start profile update background process (non-puppet only)
        # This runs throughout the agent's lifetime for SCD Type 2 tracking
        self._env.process(self._profile_update_loop())

        # Set initial random location in São Paulo if not already set
        if self._location is None:
            self._location = self._generate_random_location()

        while True:
            if self._status == "in_trip":
                if self._location:
                    # Use trip_id as correlation if in trip, otherwise rider_id
                    correlation = self._active_trip or self._rider_id
                    gps_event = EventFactory.create(
                        GPSPingEvent,
                        correlation_id=correlation,
                        entity_type="rider",
                        entity_id=self._rider_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        location=self._location,
                        heading=None,
                        speed=None,
                        accuracy=5.0,
                        trip_id=self._active_trip,
                    )

                    main_loop = None
                    if self._simulation_engine:
                        main_loop = self._simulation_engine.get_event_loop()
                    run_coroutine_safe(
                        self._emit_event(
                            event=gps_event,
                            kafka_topic="gps_pings",
                            partition_key=self._rider_id,
                            redis_channel="rider-updates",
                        ),
                        main_loop,
                        fallback_sync=True,
                    )

                yield self._env.timeout(GPS_PING_INTERVAL_MOVING)
                continue

            if self._status != "offline":
                yield self._env.timeout(GPS_PING_INTERVAL_MOVING)
                continue

            # Skip initial wait if immediate_first_trip=True (for first trip only)
            if self._immediate_first_trip and not self._first_trip_done:
                self._first_trip_done = True
                # Small delay to let simulation stabilize
                yield self._env.timeout(1)
            else:
                interval_hours = (7 * 24) / self._dna.avg_rides_per_week
                variance = random.uniform(0.8, 1.2)
                wait_time = interval_hours * 3600 * variance

                # First trip: randomize within interval so riders spread out
                if not self._first_trip_done:
                    self._first_trip_done = True
                    wait_time = random.uniform(0, wait_time)

                # Track: waiting to request next ride
                self._next_action = NextAction(
                    action_type=NextActionType.REQUEST_RIDE,
                    scheduled_at=self._env.now + wait_time,
                    description="Request next ride",
                )
                yield self._env.timeout(wait_time)

            if self._location is None:
                continue

            destination = self.select_destination()
            trip_id = str(uuid.uuid4())

            self.request_trip(trip_id)

            # Determine zones and calculate fare
            pickup_zone_id = self._determine_zone(self._location) or "unknown"

            # Track pending request for surge calculation
            if self._surge_calculator and pickup_zone_id != "unknown":
                self._surge_calculator.increment_pending_request(pickup_zone_id)
            dropoff_zone_id = self._determine_zone(destination) or "unknown"
            surge_multiplier = self._get_surge(pickup_zone_id)
            fare = self._calculate_fare(self._location, destination, surge_multiplier)

            # Emit trip.requested event (root event for this trip)
            trip_event = EventFactory.create(
                TripEvent,
                correlation_id=trip_id,
                event_type="trip.requested",
                trip_id=trip_id,
                timestamp=datetime.now(UTC).isoformat(),
                rider_id=self._rider_id,
                driver_id=None,
                pickup_location=self._location,
                dropoff_location=destination,
                pickup_zone_id=pickup_zone_id,
                dropoff_zone_id=dropoff_zone_id,
                surge_multiplier=surge_multiplier,
                fare=fare,
            )

            main_loop = None
            if self._simulation_engine:
                main_loop = self._simulation_engine.get_event_loop()
            run_coroutine_safe(
                self._emit_event(
                    event=trip_event,
                    kafka_topic="trips",
                    partition_key=trip_id,
                    redis_channel="trip-updates",
                ),
                main_loop,
                fallback_sync=True,
            )

            # Trigger matching through the simulation engine (thread-safe)
            if self._simulation_engine:
                main_loop = self._simulation_engine.get_event_loop()
                if main_loop is not None:
                    try:
                        match_coro = self._simulation_engine.request_match(
                            rider_id=self._rider_id,
                            pickup_location=self._location,
                            dropoff_location=destination,
                            pickup_zone_id=pickup_zone_id,
                            dropoff_zone_id=dropoff_zone_id,
                            surge_multiplier=surge_multiplier,
                            fare=fare,
                            trip_id=trip_id,
                        )
                        # Schedule coroutine on main thread's event loop from SimPy thread
                        asyncio.run_coroutine_threadsafe(match_coro, main_loop)
                    except ValueError as e:
                        # Simulation is pausing
                        logger.warning(f"Cannot request match: {e}")
                    except Exception as e:
                        logger.error(f"Failed to request match: {e}")
                else:
                    logger.warning("Event loop not available, cannot request match")

            match_timeout = self._env.now + self._dna.patience_threshold

            # Track: waiting for match with patience timeout
            self._next_action = NextAction(
                action_type=NextActionType.PATIENCE_TIMEOUT,
                scheduled_at=match_timeout,
                description="Cancel if no driver matched",
            )

            while self._env.now < match_timeout:
                if self._status == "in_trip":
                    self._next_action = None  # Clear - trip started
                    break

                yield self._env.timeout(1)

            if self._status == "waiting":
                self._next_action = None  # Clear - cancelling trip
                self.cancel_trip()
                self.statistics.record_request_timed_out()

                # Decrement pending request count for surge calculation
                if self._surge_calculator and pickup_zone_id != "unknown":
                    self._surge_calculator.decrement_pending_request(pickup_zone_id)

                # Cancel trip in matching server to clean up _active_trips
                if self._simulation_engine and hasattr(self._simulation_engine, "_matching_server"):
                    matching_server = self._simulation_engine._matching_server
                    if matching_server:
                        matching_server.cancel_trip(trip_id, "rider", "patience_timeout")

                event = EventFactory.create(
                    TripEvent,
                    correlation_id=trip_id,
                    event_type="trip.cancelled",
                    trip_id=trip_id,
                    timestamp=datetime.now(UTC).isoformat(),
                    rider_id=self._rider_id,
                    driver_id=None,
                    pickup_location=self._location,
                    dropoff_location=destination,
                    pickup_zone_id=pickup_zone_id,
                    dropoff_zone_id=dropoff_zone_id,
                    surge_multiplier=surge_multiplier,
                    fare=fare,
                    cancelled_by="rider",
                    cancellation_reason="patience_timeout",
                )

                main_loop = None
                if self._simulation_engine:
                    main_loop = self._simulation_engine.get_event_loop()
                run_coroutine_safe(
                    self._emit_event(
                        event=event,
                        kafka_topic="trips",
                        partition_key=trip_id,
                        redis_channel="trip-updates",
                    ),
                    main_loop,
                    fallback_sync=True,
                )
                continue

            while self._status == "in_trip":
                if self._location:
                    # Use trip_id as correlation since rider is in trip
                    correlation = self._active_trip or self._rider_id
                    gps_event = EventFactory.create(
                        GPSPingEvent,
                        correlation_id=correlation,
                        entity_type="rider",
                        entity_id=self._rider_id,
                        timestamp=datetime.now(UTC).isoformat(),
                        location=self._location,
                        heading=None,
                        speed=None,
                        accuracy=5.0,
                        trip_id=self._active_trip,
                    )

                    main_loop = None
                    if self._simulation_engine:
                        main_loop = self._simulation_engine.get_event_loop()
                    run_coroutine_safe(
                        self._emit_event(
                            event=gps_event,
                            kafka_topic="gps_pings",
                            partition_key=self._rider_id,
                            redis_channel="rider-updates",
                        ),
                        main_loop,
                        fallback_sync=True,
                    )

                yield self._env.timeout(GPS_PING_INTERVAL_MOVING)

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

    def _get_surge(self, zone_id: str) -> float:
        """Get current surge multiplier for a zone.

        Args:
            zone_id: The zone ID to get surge for

        Returns:
            Surge multiplier (defaults to 1.0 if unavailable)
        """
        if not self._surge_calculator:
            return 1.0
        return self._surge_calculator.get_surge(zone_id)

    def _calculate_fare(
        self,
        pickup: tuple[float, float],
        dropoff: tuple[float, float],
        surge_multiplier: float,
    ) -> float:
        """Calculate fare for a trip.

        Args:
            pickup: (lat, lon) of pickup location
            dropoff: (lat, lon) of dropoff location
            surge_multiplier: Current surge multiplier

        Returns:
            Calculated fare amount
        """
        # Base fare calculation
        BASE_FARE = 5.0  # BRL
        PER_KM_RATE = 2.5  # BRL per km
        PER_MINUTE_RATE = 0.5  # BRL per minute

        # Calculate distance using OSRM if available, otherwise Haversine
        if self._osrm_client:
            try:
                route = asyncio.run(self._osrm_client.get_route(pickup, dropoff))
                distance_km = route.distance_meters / 1000
                duration_minutes = route.duration_seconds / 60
            except Exception:
                # Fallback to Haversine estimate
                distance_km = self._haversine_distance(pickup[0], pickup[1], dropoff[0], dropoff[1])
                # Estimate duration based on average city speed (25 km/h)
                duration_minutes = (distance_km / 25) * 60
        else:
            distance_km = self._haversine_distance(pickup[0], pickup[1], dropoff[0], dropoff[1])
            duration_minutes = (distance_km / 25) * 60

        # Calculate total fare
        fare = BASE_FARE + (distance_km * PER_KM_RATE) + (duration_minutes * PER_MINUTE_RATE)
        fare = fare * surge_multiplier

        # Round to 2 decimal places
        return round(fare, 2)

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers using Haversine formula."""
        import math

        R = 6371  # Earth radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

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
            Dictionary containing rider state
        """
        zone_id = None
        loader = zone_loader or self._zone_loader
        if loader and self._location:
            zone_id = loader.find_zone_for_location(self._location[0], self._location[1])

        return {
            "rider_id": self._rider_id,
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
        agent._statistics = RiderStatistics()  # Session-only, not persisted

        return agent
