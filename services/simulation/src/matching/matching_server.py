"""Matching server that coordinates driver-rider matching."""

import asyncio
import logging
import threading
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from uuid import uuid4

import simpy

from events.factory import EventFactory
from events.schemas import TripEvent
from kafka.serializer_registry import SerializerRegistry
from matching.driver_geospatial_index import DriverGeospatialIndex
from puppet.drive_controller import PuppetDriveController
from settings import Settings
from trip import Trip, TripState
from trips.trip_executor import TripExecutor

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient, RouteResponse
    from kafka.producer import KafkaProducer
    from matching.agent_registry_manager import AgentRegistryManager
    from matching.surge_pricing import SurgePricingCalculator
    from redis_client.publisher import RedisPublisher

logger = logging.getLogger(__name__)

# Type alias for trip event types
TripEventType = Literal[
    "trip.requested",
    "trip.offer_sent",
    "trip.matched",
    "trip.driver_en_route",
    "trip.driver_arrived",
    "trip.started",
    "trip.completed",
    "trip.cancelled",
    "trip.offer_expired",
    "trip.offer_rejected",
    "trip.no_drivers_available",
]

# Type alias for cancellation actor
CancellationActor = Literal["rider", "driver", "system"]


class PendingOffer(TypedDict):
    """Structure for a pending trip offer to a driver."""

    trip_id: str
    surge_multiplier: float
    rider_rating: float
    eta_seconds: int


class PendingOfferCandidates(TypedDict):
    """Structure for tracking remaining candidates during offer cycle."""

    remaining_drivers: list[tuple[Any, int, float]]  # (DriverAgent, eta, score)
    current_attempt: int
    max_attempts: int


class PuppetDriveStatus(TypedDict):
    """Structure for puppet drive status."""

    is_running: bool
    is_completed: bool


class MatchingServer:
    """Coordinates driver-rider matching with composite scoring.

    Thread-safe: Shared state (active trips, pending offers, counters) is
    protected by an RLock for concurrent access from the SimPy background
    thread and FastAPI main thread.
    """

    def __init__(
        self,
        env: simpy.Environment,
        driver_index: DriverGeospatialIndex,
        notification_dispatch: Any,
        osrm_client: "OSRMClient",
        kafka_producer: "KafkaProducer | None" = None,
        registry_manager: "AgentRegistryManager | None" = None,
        redis_publisher: "RedisPublisher | None" = None,
        surge_calculator: "SurgePricingCalculator | None" = None,
        settings: Settings | None = None,
        simulation_engine: "SimulationEngine | None" = None,
    ):
        self._env = env
        self._driver_index = driver_index
        self._notification_dispatch = notification_dispatch
        self._osrm_client = osrm_client
        self._kafka_producer = kafka_producer
        self._registry_manager = registry_manager
        self._redis_publisher = redis_publisher
        self._surge_calculator = surge_calculator
        self._settings = settings or Settings()
        self._simulation_engine = simulation_engine
        self._pending_offers: dict[str, PendingOffer] = {}
        # Store remaining candidates when puppet driver gets offer (for continuation after rejection)
        self._pending_offer_candidates: dict[str, PendingOfferCandidates] = {}
        self._drivers: dict[str, DriverAgent] = {}
        self._active_trips: dict[str, Trip] = {}
        # Queue for trips that need their TripExecutor started from SimPy thread
        self._pending_trip_executions: list[tuple[DriverAgent, Trip]] = []
        # Trip completion tracking (bounded deques to prevent memory growth)
        self._completed_trips: deque[Trip] = deque(maxlen=self._settings.matching.max_trip_history)
        self._cancelled_trips: deque[Trip] = deque(maxlen=self._settings.matching.max_trip_history)
        # Thread-safe state protection (RLock allows nested acquisition)
        self._state_lock = threading.RLock()
        self._reserved_drivers: set[str] = set()  # Drivers currently receiving offers
        # Matching outcome tracking
        self._offers_sent: int = 0
        self._offers_accepted: int = 0
        self._offers_rejected: int = 0
        self._offers_expired: int = 0
        # Running accumulators for O(1) trip stats (updated in complete_trip)
        self._stats_total_fare: float = 0.0
        self._stats_duration_sum: float = 0.0
        self._stats_duration_count: int = 0
        self._stats_wait_sum: float = 0.0
        self._stats_wait_count: int = 0
        self._stats_pickup_sum: float = 0.0
        self._stats_pickup_count: int = 0
        # Limit how many drivers get OSRM route fetches (top-N by haversine distance)
        self._osrm_candidate_limit: int = 15
        # Puppet drive controllers (for background thread movement)
        self._puppet_drives: dict[str, PuppetDriveController] = {}

    def register_driver(self, driver: "DriverAgent") -> None:
        self._drivers[driver.driver_id] = driver

    def unregister_driver(self, driver_id: str) -> None:
        self._drivers.pop(driver_id, None)

    def get_active_trips(self) -> list[Trip]:
        """Get all active (non-completed/cancelled) trips."""
        with self._state_lock:
            return list(self._active_trips.values())

    def complete_trip(self, trip_id: str, trip: "Trip | None" = None) -> None:
        """Remove trip from active tracking and record completion/cancellation.

        Args:
            trip_id: The trip ID to complete
            trip: Optional trip object with final state for tracking
        """
        with self._state_lock:
            removed_trip = self._active_trips.pop(trip_id, None)

            # Use provided trip or the removed one for tracking
            tracking_trip = trip or removed_trip
            if tracking_trip:
                if tracking_trip.state.value == "cancelled":
                    self._cancelled_trips.append(tracking_trip)
                elif tracking_trip.state.value == "completed":
                    self._completed_trips.append(tracking_trip)
                    self._accumulate_trip_stats(tracking_trip)

    def get_completed_trips(self) -> list["Trip"]:
        """Get all completed trips."""
        with self._state_lock:
            return list(self._completed_trips)

    def get_cancelled_trips(self) -> list["Trip"]:
        """Get all cancelled trips."""
        with self._state_lock:
            return list(self._cancelled_trips)

    def _accumulate_trip_stats(self, trip: "Trip") -> None:
        """Update running accumulators when a trip completes.

        Must be called under _state_lock.
        """
        if trip.fare:
            self._stats_total_fare += trip.fare

        if trip.matched_at and trip.completed_at:
            duration = (trip.completed_at - trip.matched_at).total_seconds() / 60
            self._stats_duration_sum += duration
            self._stats_duration_count += 1

        if trip.requested_at and trip.driver_arrived_at:
            wait_seconds = (trip.driver_arrived_at - trip.requested_at).total_seconds()
            self._stats_wait_sum += wait_seconds
            self._stats_wait_count += 1

        if trip.matched_at and trip.driver_arrived_at:
            pickup_seconds = (trip.driver_arrived_at - trip.matched_at).total_seconds()
            self._stats_pickup_sum += pickup_seconds
            self._stats_pickup_count += 1

    def get_trip_stats(self) -> dict[str, Any]:
        """Get trip statistics for metrics using running accumulators (O(1))."""
        with self._state_lock:
            completed_count = len(self._completed_trips)
            cancelled_count = len(self._cancelled_trips)
            total_fare = self._stats_total_fare
            duration_sum = self._stats_duration_sum
            duration_count = self._stats_duration_count
            wait_sum = self._stats_wait_sum
            wait_count = self._stats_wait_count
            pickup_sum = self._stats_pickup_sum
            pickup_count = self._stats_pickup_count

        avg_fare = total_fare / completed_count if completed_count > 0 else 0.0
        avg_duration = duration_sum / duration_count if duration_count > 0 else 0.0
        avg_wait_seconds = wait_sum / wait_count if wait_count > 0 else 0.0
        avg_pickup_seconds = pickup_sum / pickup_count if pickup_count > 0 else 0.0

        return {
            "completed_count": completed_count,
            "cancelled_count": cancelled_count,
            "avg_fare": avg_fare,
            "avg_duration_minutes": avg_duration,
            "avg_wait_seconds": avg_wait_seconds,
            "avg_pickup_seconds": avg_pickup_seconds,
        }

    def get_matching_stats(self) -> dict[str, Any]:
        """Get matching outcome statistics for metrics."""
        with self._state_lock:
            return {
                "offers_sent": self._offers_sent,
                "offers_accepted": self._offers_accepted,
                "offers_rejected": self._offers_rejected,
                "offers_expired": self._offers_expired,
            }

    async def request_match(
        self,
        rider_id: str,
        pickup_location: tuple[float, float],
        dropoff_location: tuple[float, float],
        pickup_zone_id: str,
        dropoff_zone_id: str,
        surge_multiplier: float,
        fare: float,
        trip_id: str | None = None,
    ) -> Trip | None:
        logger.info(
            f"request_match called: rider={rider_id}, pickup={pickup_location}, trip_id={trip_id}"
        )
        trip = Trip(
            trip_id=trip_id or str(uuid4()),
            rider_id=rider_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
            requested_at=self._current_time(),
        )

        # Compute route immediately for early visualization (pending route)
        try:
            route_response = await self._osrm_client.get_route(pickup_location, dropoff_location)
            trip.route = route_response.geometry
            logger.info(f"Trip {trip.trip_id}: Computed route with {len(trip.route)} points")
        except Exception as e:
            logger.warning(f"Trip {trip.trip_id}: Could not fetch route at request time: {e}")

        # Track trip as active immediately so it appears in snapshots
        self._active_trips[trip.trip_id] = trip

        logger.info(f"Finding nearby drivers for trip {trip.trip_id}")
        nearby_drivers = await self.find_nearby_drivers(pickup_location)
        logger.info(f"Found {len(nearby_drivers)} nearby drivers")
        if not nearby_drivers:
            logger.warning(f"No nearby drivers found for trip {trip.trip_id}")
            self._emit_no_drivers_event(trip)
            # Remove from active trips since no match will happen
            self._active_trips.pop(trip.trip_id, None)
            return None

        ranked_drivers = self.rank_drivers(nearby_drivers)
        logger.info(f"Ranked {len(ranked_drivers)} drivers, sending offers")

        result = self.send_offer_cycle(trip, ranked_drivers)
        logger.info(f"send_offer_cycle result: {result}")
        return result

    async def find_nearby_drivers(
        self,
        pickup_location: tuple[float, float],
        max_eta_seconds: int = 900,
    ) -> list[tuple["DriverAgent", int]]:
        logger.debug(f"Searching for nearby drivers at {pickup_location}")
        logger.debug(f"Driver index has {len(self._driver_index._driver_locations)} drivers total")
        logger.debug(f"Drivers registered with matching server: {len(self._drivers)}")

        nearby = self._driver_index.find_nearest_drivers(
            pickup_location[0],
            pickup_location[1],
            radius_km=10.0,
            status_filter="online",
        )
        logger.debug(f"Spatial index returned {len(nearby)} nearby online drivers")

        # Filter to valid drivers with locations
        valid_drivers: list[tuple[DriverAgent, float]] = []
        for driver_id, distance_km in nearby:
            logger.debug(f"Processing driver {driver_id}, distance={distance_km:.2f}km")
            driver = self._drivers.get(driver_id)
            if not driver or not driver.location:
                logger.warning(f"Driver {driver_id} not found or has no location")
                continue
            logger.debug(f"Driver {driver_id} location: {driver.location}")
            valid_drivers.append((driver, distance_km))

        if not valid_drivers:
            logger.info("No valid drivers with locations found")
            return []

        # Sort by haversine distance (already sorted from spatial index) and
        # limit to top-N candidates to avoid unnecessary OSRM calls
        valid_drivers = valid_drivers[: self._osrm_candidate_limit]

        # Fetch all routes in parallel
        async def fetch_route(
            driver: "DriverAgent",
        ) -> tuple["DriverAgent", int] | None:
            try:
                # Location is guaranteed non-None by valid_drivers filter above
                assert driver.location is not None
                route = await self._osrm_client.get_route(driver.location, pickup_location)
                eta_seconds = int(route.duration_seconds)
                logger.debug(
                    f"Driver {driver.driver_id} ETA: {eta_seconds}s (max={max_eta_seconds}s)"
                )
                if eta_seconds <= max_eta_seconds:
                    logger.debug(f"Driver {driver.driver_id} added to result (ETA within limit)")
                    return (driver, eta_seconds)
                else:
                    logger.debug(f"Driver {driver.driver_id} ETA too long, skipping")
                    return None
            except Exception as e:
                logger.error(f"Failed to get route for driver {driver.driver_id}: {e}")
                return None

        route_results = await asyncio.gather(*[fetch_route(driver) for driver, _ in valid_drivers])

        # Filter out None results (failed fetches or ETAs too long)
        result = [r for r in route_results if r is not None]

        logger.info(f"Found {len(result)} drivers with valid ETAs")
        return result

    def rank_drivers(
        self,
        driver_eta_list: list[tuple["DriverAgent", int]],
    ) -> list[tuple["DriverAgent", int, float]]:
        if not driver_eta_list:
            return []

        etas = [eta for _, eta in driver_eta_list]
        min_eta = min(etas)
        max_eta = max(etas)

        # Extract weights once before loop to avoid repeated attribute chain traversal
        eta_weight = self._settings.matching.ranking_eta_weight
        rating_weight = self._settings.matching.ranking_rating_weight
        acceptance_weight = self._settings.matching.ranking_acceptance_weight

        scored = []
        for driver, eta in driver_eta_list:
            score = self._calculate_composite_score(
                eta_seconds=eta,
                rating=driver.current_rating,
                acceptance_rate=driver.dna.acceptance_rate,
                min_eta=min_eta,
                max_eta=max_eta,
                eta_weight=eta_weight,
                rating_weight=rating_weight,
                acceptance_weight=acceptance_weight,
            )
            scored.append((driver, eta, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored

    def _calculate_composite_score(
        self,
        eta_seconds: int,
        rating: float,
        acceptance_rate: float,
        min_eta: int,
        max_eta: int,
        eta_weight: float,
        rating_weight: float,
        acceptance_weight: float,
    ) -> float:
        # Normalize ETA (lower is better, so invert)
        if max_eta == min_eta:
            eta_normalized = 1.0
        else:
            eta_normalized = (max_eta - eta_seconds) / (max_eta - min_eta)

        # Normalize rating (1.0-5.0 scale to 0.0-1.0)
        rating_normalized = (rating - 1.0) / 4.0

        # Acceptance rate is already 0.0-1.0
        acceptance_normalized = acceptance_rate

        # Composite score using pre-extracted weights
        score: float = (
            eta_normalized * eta_weight
            + rating_normalized * rating_weight
            + acceptance_normalized * acceptance_weight
        )
        return score

    def send_offer_cycle(
        self,
        trip: Trip,
        ranked_drivers: list[tuple["DriverAgent", int, float]],
        max_attempts: int = 5,
    ) -> Trip | None:
        logger.info(f"send_offer_cycle: {len(ranked_drivers)} drivers, max_attempts={max_attempts}")
        for attempts, (driver, eta_seconds, _score) in enumerate(ranked_drivers):
            if attempts >= max_attempts:
                logger.info(f"Reached max attempts ({max_attempts})")
                break

            logger.info(f"Sending offer to driver {driver.driver_id} (attempt {attempts + 1})")
            accepted = self.send_offer(driver, trip, trip.offer_sequence + 1, eta_seconds)

            # For puppet drivers, pause the cycle and wait for manual accept/reject via API
            if getattr(driver, "_is_puppet", False):
                logger.info(
                    f"Puppet driver {driver.driver_id} has pending offer for trip {trip.trip_id}, "
                    "pausing cycle and waiting for API action"
                )
                # Store remaining candidates for continuation after puppet decision
                remaining = ranked_drivers[attempts + 1 :]
                self._pending_offer_candidates[trip.trip_id] = {
                    "remaining_drivers": remaining,
                    "current_attempt": attempts + 1,
                    "max_attempts": max_attempts,
                }
                # Track trip as active but waiting for puppet decision
                self._active_trips[trip.trip_id] = trip
                # Return trip to indicate it's pending (not None which would mean failure)
                return trip

            logger.info(f"Driver {driver.driver_id} {'accepted' if accepted else 'rejected'} offer")

            if accepted:
                trip.driver_id = driver.driver_id
                trip.transition_to(TripState.MATCHED)
                trip.matched_at = self._current_time()
                self._emit_matched_event(trip)

                # Track active trip
                self._active_trips[trip.trip_id] = trip
                logger.info(
                    f"Trip {trip.trip_id} matched with driver {driver.driver_id}, tracking as active"
                )

                # Decrement pending request count for surge calculation
                if self._surge_calculator:
                    self._surge_calculator.decrement_pending_request(trip.pickup_zone_id)

                # Start trip execution
                logger.info(f"Starting trip execution for trip {trip.trip_id}")
                self._start_trip_execution(driver, trip)

                return trip

            # Transition to rejected for next offer
            trip.transition_to(TripState.OFFER_REJECTED)

        logger.warning(f"All offers rejected for trip {trip.trip_id}")
        self._emit_no_drivers_event(trip)
        # Remove from active trips since no match happened
        self._active_trips.pop(trip.trip_id, None)
        return None

    def _continue_offer_cycle(
        self,
        trip: Trip,
        remaining_drivers: list[tuple["DriverAgent", int, float]],
        start_attempt: int,
        max_attempts: int,
    ) -> Trip | None:
        """Continue the offer cycle with remaining drivers after puppet rejection.

        This is called when a puppet driver rejects or times out to resume
        the offer cycle with the remaining ranked candidates.

        Args:
            trip: The trip to match
            remaining_drivers: List of (driver, eta_seconds, score) tuples
            start_attempt: The attempt number to start from
            max_attempts: Maximum total attempts allowed

        Returns:
            The matched trip if successful, None if all attempts exhausted
        """
        logger.info(
            f"Continuing offer cycle for trip {trip.trip_id} with "
            f"{len(remaining_drivers)} remaining drivers from attempt {start_attempt}"
        )

        for idx, (driver, eta_seconds, _score) in enumerate(remaining_drivers):
            attempt_num = start_attempt + idx
            if attempt_num >= max_attempts:
                logger.info(f"Reached max attempts ({max_attempts})")
                break

            logger.info(f"Sending offer to driver {driver.driver_id} (attempt {attempt_num + 1})")
            accepted = self.send_offer(driver, trip, trip.offer_sequence + 1, eta_seconds)

            # For puppet drivers, pause the cycle again and wait for manual action
            if getattr(driver, "_is_puppet", False):
                logger.info(
                    f"Puppet driver {driver.driver_id} has pending offer for trip {trip.trip_id}, "
                    "pausing cycle and waiting for API action"
                )
                # Store remaining candidates after this puppet driver
                further_remaining = remaining_drivers[idx + 1 :]
                self._pending_offer_candidates[trip.trip_id] = {
                    "remaining_drivers": further_remaining,
                    "current_attempt": attempt_num + 1,
                    "max_attempts": max_attempts,
                }
                return trip

            logger.info(f"Driver {driver.driver_id} {'accepted' if accepted else 'rejected'} offer")

            if accepted:
                trip.driver_id = driver.driver_id
                trip.transition_to(TripState.MATCHED)
                trip.matched_at = self._current_time()
                self._emit_matched_event(trip)

                logger.info(
                    f"Trip {trip.trip_id} matched with driver {driver.driver_id}, tracking as active"
                )

                # Decrement pending request count for surge calculation
                if self._surge_calculator:
                    self._surge_calculator.decrement_pending_request(trip.pickup_zone_id)

                # Start trip execution
                logger.info(f"Starting trip execution for trip {trip.trip_id}")
                self._start_trip_execution(driver, trip)

                return trip

            # Transition to rejected for next offer
            trip.transition_to(TripState.OFFER_REJECTED)

        logger.warning(f"All remaining offers rejected for trip {trip.trip_id}")
        return None

    def _start_trip_execution(self, driver: "DriverAgent", trip: Trip) -> None:
        """Queue trip execution to be started from SimPy thread.

        This is called from the async context, so we queue the trip
        for thread-safe processing. The SimPy thread will pick it up
        via start_pending_trip_executions().

        Args:
            driver: The matched driver
            trip: The matched trip
        """
        logger.info(f"Queueing trip execution for trip {trip.trip_id}")
        with self._state_lock:
            self._pending_trip_executions.append((driver, trip))

    def start_pending_trip_executions(self) -> None:
        """Start any pending trip executions. Must be called from SimPy thread.

        This is called from SimulationEngine.step() to safely start
        TripExecutor processes within the SimPy thread context.
        """
        with self._state_lock:
            pending = list(self._pending_trip_executions)
            self._pending_trip_executions.clear()

        if pending:
            logger.info(f"Starting {len(pending)} pending trip executions")
        for driver, trip in pending:
            logger.info(f"Starting TripExecutor for trip {trip.trip_id}")
            self._start_trip_execution_internal(driver, trip)

    def _start_trip_execution_internal(self, driver: "DriverAgent", trip: Trip) -> None:
        """Actually start the TripExecutor. Must be called from SimPy thread.

        Args:
            driver: The matched driver
            trip: The matched trip
        """
        logger.debug("_start_trip_execution_internal called", extra={"trip_id": trip.trip_id})
        if not self._registry_manager:
            logger.debug("No registry_manager available", extra={"trip_id": trip.trip_id})
            return

        rider = self._registry_manager.get_rider(trip.rider_id)
        if not rider:
            logger.debug(
                "Rider not found",
                extra={"trip_id": trip.trip_id, "rider_id": trip.rider_id},
            )
            return

        logger.debug("Creating TripExecutor", extra={"trip_id": trip.trip_id})
        executor = TripExecutor(
            env=self._env,
            driver=driver,
            rider=rider,
            trip=trip,
            osrm_client=self._osrm_client,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            matching_server=self,
            settings=self._settings.simulation if self._settings else None,
            simulation_engine=self._simulation_engine,
        )

        # Start the trip execution as a SimPy process
        logger.debug("Starting SimPy process", extra={"trip_id": trip.trip_id})
        self._env.process(executor.execute())
        logger.debug("SimPy process started", extra={"trip_id": trip.trip_id})

    def send_offer(
        self,
        driver: "DriverAgent",
        trip: Trip,
        offer_sequence: int,
        eta_seconds: int,
    ) -> bool:
        driver_id = driver.driver_id

        # Atomic check-and-reserve to prevent double-matching
        with self._state_lock:
            # Skip if driver already reserved or in a trip
            if driver_id in self._reserved_drivers:
                logger.warning(f"Driver {driver_id} already reserved, skipping")
                return False
            if driver.active_trip:
                logger.warning(f"Driver {driver_id} already has active trip, skipping")
                return False

            # Reserve this driver (prevents double-matching without changing status)
            self._reserved_drivers.add(driver_id)

        trip.transition_to(TripState.OFFER_SENT)
        self._offers_sent += 1
        # Track offer in driver's statistics
        driver.statistics.record_offer_received()
        self._emit_offer_sent_event(trip, driver_id, offer_sequence, eta_seconds)

        # For puppet drivers, store offer and wait for manual action via API
        # Reservation stays active — puppet accept/reject handles release
        if getattr(driver, "_is_puppet", False):
            rider = (
                self._registry_manager.get_rider(trip.rider_id) if self._registry_manager else None
            )
            rider_rating = rider.current_rating if rider else 5.0
            self._pending_offers[driver_id] = {
                "trip_id": trip.trip_id,
                "surge_multiplier": trip.surge_multiplier,
                "rider_rating": rider_rating,
                "eta_seconds": eta_seconds,
            }
            # Return False to pause matching cycle - puppet will accept/reject via API
            return False

        # Regular drivers auto-decide based on DNA
        try:
            accepted: bool = self._notification_dispatch.send_driver_offer(
                driver=driver,
                trip=trip,
                eta_seconds=eta_seconds,
            )
        except Exception:
            # Release reservation on error
            with self._state_lock:
                self._reserved_drivers.discard(driver_id)
                self._driver_index.update_driver_status(driver_id, "online")
            raise

        # Track acceptance/rejection (global and per-driver)
        if accepted:
            self._offers_accepted += 1
            driver.statistics.record_offer_accepted()
        else:
            self._offers_rejected += 1
            driver.statistics.record_offer_rejected()

        # Release reservation: accepted drivers are tracked via active_trip,
        # rejected drivers go back to the available pool
        with self._state_lock:
            self._reserved_drivers.discard(driver_id)
            if not accepted:
                self._driver_index.update_driver_status(driver_id, "online")

        return accepted

    def _format_timestamp(self) -> str:
        """Format current timestamp using simulated time if available."""
        if self._simulation_engine:
            result = self._simulation_engine.time_manager.format_timestamp()
            if isinstance(result, str):
                return result
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _current_time(self) -> datetime:
        """Get current time using simulated time if available."""
        if self._simulation_engine:
            result = self._simulation_engine.time_manager.current_time()
            if isinstance(result, datetime):
                return result
        return datetime.now(UTC)

    def _publish_trip_event(self, event: TripEvent, trip_id: str) -> None:
        """Publish a trip event to Kafka with optional schema validation.

        Uses SerializerRegistry if Schema Registry is enabled, otherwise
        falls back to direct JSON serialization.
        """
        if not self._kafka_producer:
            return

        serializer = SerializerRegistry.get_serializer("trips")
        if serializer:
            json_str, _ = serializer.serialize_for_kafka(event, "trips")
        else:
            json_str = event.model_dump_json()

        self._kafka_producer.produce(
            topic="trips",
            key=trip_id,
            value=json_str,
        )

    def _emit_offer_sent_event(
        self,
        trip: Trip,
        driver_id: str,
        offer_sequence: int,
        eta_seconds: int,
    ) -> None:
        if not self._kafka_producer:
            return

        event = EventFactory.create_for_trip(
            TripEvent,
            trip,
            update_causation=True,
            event_type="trip.offer_sent",
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=driver_id,
            pickup_location=trip.pickup_location,
            dropoff_location=trip.dropoff_location,
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            offer_sequence=offer_sequence,
            timestamp=self._format_timestamp(),
        )

        self._publish_trip_event(event, trip.trip_id)

    def _emit_matched_event(self, trip: Trip) -> None:
        if not self._kafka_producer:
            return

        event = EventFactory.create_for_trip(
            TripEvent,
            trip,
            update_causation=True,
            event_type="trip.matched",
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=trip.driver_id,
            pickup_location=trip.pickup_location,
            dropoff_location=trip.dropoff_location,
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            offer_sequence=trip.offer_sequence,
            timestamp=self._format_timestamp(),
        )

        self._publish_trip_event(event, trip.trip_id)

    def _emit_no_drivers_event(self, trip: Trip) -> None:
        if not self._kafka_producer:
            return

        event = TripEvent(
            event_type="trip.no_drivers_available",
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=None,
            pickup_location=trip.pickup_location,
            dropoff_location=trip.dropoff_location,
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            offer_sequence=trip.offer_sequence,
            timestamp=self._format_timestamp(),
        )

        self._publish_trip_event(event, trip.trip_id)

    def clear(self) -> None:
        """Clear all matching server state for simulation reset."""
        with self._state_lock:
            # Stop any active puppet drives
            for controller in self._puppet_drives.values():
                controller.stop()
            self._puppet_drives.clear()

            self._active_trips.clear()
            # Reinitialize deques with maxlen to ensure bound is preserved
            self._completed_trips = deque(maxlen=self._settings.matching.max_trip_history)
            self._cancelled_trips = deque(maxlen=self._settings.matching.max_trip_history)
            self._pending_offers.clear()
            self._pending_offer_candidates.clear()
            self._pending_trip_executions.clear()
            self._drivers.clear()
            self._reserved_drivers.clear()
            # Reset matching counters
            self._offers_sent = 0
            self._offers_accepted = 0
            self._offers_rejected = 0
            self._offers_expired = 0
            # Reset trip stats accumulators
            self._stats_total_fare = 0.0
            self._stats_duration_sum = 0.0
            self._stats_duration_count = 0
            self._stats_wait_sum = 0.0
            self._stats_wait_count = 0
            self._stats_pickup_sum = 0.0
            self._stats_pickup_count = 0

            # Clear the geospatial index
            if hasattr(self._driver_index, "clear"):
                self._driver_index.clear()

    # --- Puppet Agent Helper Methods ---

    def get_pending_offer_for_driver(self, driver_id: str) -> PendingOffer | None:
        """Get the pending trip offer for a specific driver."""
        with self._state_lock:
            return self._pending_offers.get(driver_id)

    def process_puppet_accept(self, driver_id: str, trip_id: str) -> None:
        """Process offer acceptance for a puppet driver.

        This manually accepts an offer that was waiting for user action.
        """
        offer = self._pending_offers.pop(driver_id, None)
        if not offer:
            return

        trip = self._active_trips.get(trip_id)
        if not trip:
            # Trip gone, release driver reservation and restore status
            with self._state_lock:
                self._reserved_drivers.discard(driver_id)
                self._driver_index.update_driver_status(driver_id, "online")
            return

        driver = self._drivers.get(driver_id)
        if not driver:
            return

        # Track acceptance (global and per-driver)
        self._offers_accepted += 1
        driver.statistics.record_offer_accepted()

        # Clear reservation (driver is now in active trip)
        with self._state_lock:
            self._reserved_drivers.discard(driver_id)

        # Update trip state
        driver.accept_trip(trip_id)
        driver.start_pickup()  # Transition to en_route_pickup
        trip.driver_id = driver_id
        trip.transition_to(TripState.MATCHED)
        trip.matched_at = self._current_time()
        self._emit_matched_event(trip)

        # Transition to DRIVER_EN_ROUTE for puppet flow
        trip.transition_to(TripState.DRIVER_EN_ROUTE)

        # Note: Do NOT start TripExecutor for puppet drivers.
        # Puppets are controlled entirely via API endpoints (drive-to-pickup,
        # arrive-pickup, start-trip, drive-to-destination, complete-trip, etc.)
        # rather than autonomous simulation.

    def process_puppet_reject(self, driver_id: str, trip_id: str) -> None:
        """Process offer rejection for a puppet driver and continue to next candidate.

        This manually rejects an offer and automatically continues the offer
        cycle with the remaining ranked drivers.
        """
        self._pending_offers.pop(driver_id, None)

        driver = self._drivers.get(driver_id)

        # Track rejection (global and per-driver)
        self._offers_rejected += 1
        if driver:
            driver.statistics.record_offer_rejected()

        # Release reservation and restore driver to matchable status
        with self._state_lock:
            self._reserved_drivers.discard(driver_id)
            self._driver_index.update_driver_status(driver_id, "online")

        trip = self._active_trips.get(trip_id)
        if not trip:
            # Clean up candidates if trip is gone
            self._pending_offer_candidates.pop(trip_id, None)
            return

        # Transition to rejected
        trip.transition_to(TripState.OFFER_REJECTED)

        # Continue to next candidate if available
        candidates_info = self._pending_offer_candidates.pop(trip_id, None)
        if candidates_info and candidates_info["remaining_drivers"]:
            result = self._continue_offer_cycle(
                trip,
                candidates_info["remaining_drivers"],
                candidates_info["current_attempt"],
                candidates_info["max_attempts"],
            )

            if result is None:
                # All candidates exhausted, emit no_drivers event
                self._emit_no_drivers_event(trip)
                self._active_trips.pop(trip.trip_id, None)
        else:
            # No more candidates available
            logger.info(f"No remaining candidates for trip {trip_id} after puppet rejection")
            self._emit_no_drivers_event(trip)
            self._active_trips.pop(trip.trip_id, None)

    def process_puppet_timeout(self, driver_id: str, trip_id: str) -> None:
        """Process offer timeout for a puppet driver and continue to next candidate.

        This handles when an offer expires without driver response and automatically
        continues the offer cycle with the remaining ranked drivers.
        """
        self._pending_offers.pop(driver_id, None)

        driver = self._drivers.get(driver_id)

        # Track expiration (global and per-driver)
        self._offers_expired += 1
        if driver:
            driver.statistics.record_offer_expired()

        # Release reservation and restore driver to matchable status
        with self._state_lock:
            self._reserved_drivers.discard(driver_id)
            self._driver_index.update_driver_status(driver_id, "online")

        trip = self._active_trips.get(trip_id)
        if not trip:
            # Clean up candidates if trip is gone
            self._pending_offer_candidates.pop(trip_id, None)
            return

        # Transition to expired
        trip.transition_to(TripState.OFFER_EXPIRED)

        # Continue to next candidate if available
        candidates_info = self._pending_offer_candidates.pop(trip_id, None)
        if candidates_info and candidates_info["remaining_drivers"]:
            result = self._continue_offer_cycle(
                trip,
                candidates_info["remaining_drivers"],
                candidates_info["current_attempt"],
                candidates_info["max_attempts"],
            )

            if result is None:
                # All candidates exhausted, emit no_drivers event
                self._emit_no_drivers_event(trip)
                self._active_trips.pop(trip.trip_id, None)
        else:
            # No more candidates available
            logger.info(f"No remaining candidates for trip {trip_id} after puppet timeout")
            self._emit_no_drivers_event(trip)
            self._active_trips.pop(trip.trip_id, None)

    def signal_driver_arrived(self, driver_id: str, trip_id: str) -> None:
        """Signal that a puppet driver has arrived at pickup location."""
        trip = self._active_trips.get(trip_id)
        if not trip:
            return

        driver = self._drivers.get(driver_id)
        if not driver:
            return

        # Transition trip to driver_arrived
        trip.transition_to(TripState.DRIVER_ARRIVED)
        self._emit_trip_state_event(trip, "trip.driver_arrived")

    def signal_trip_started(self, driver_id: str, trip_id: str) -> None:
        """Signal that a puppet trip has started (rider picked up)."""
        trip = self._active_trips.get(trip_id)
        if not trip:
            return

        driver = self._drivers.get(driver_id)
        if not driver:
            return

        # Update driver status
        driver.start_trip()

        # Update rider status
        if self._registry_manager:
            rider = self._registry_manager.get_rider(trip.rider_id)
            if rider:
                rider.start_trip()

        # Transition trip to started
        trip.transition_to(TripState.STARTED)
        trip.started_at = self._current_time()
        self._emit_trip_state_event(trip, "trip.started")

    def signal_trip_completed(self, driver_id: str, trip_id: str) -> None:
        """Signal that a puppet trip has been completed."""
        trip = self._active_trips.get(trip_id)
        if not trip:
            return

        driver = self._drivers.get(driver_id)
        if not driver:
            return

        # Update driver status
        driver.complete_trip()

        # Update rider status
        rider = None
        if self._registry_manager:
            rider = self._registry_manager.get_rider(trip.rider_id)
            if rider:
                rider.complete_trip()

        # Transition trip to completed
        trip.transition_to(TripState.COMPLETED)
        trip.completed_at = self._current_time()

        # Track trip completion statistics
        self._record_trip_completion_stats(driver, rider, trip)

        self._emit_trip_state_event(trip, "trip.completed")

        # Remove from active trips
        self.complete_trip(trip_id, trip)

    def _record_trip_completion_stats(
        self,
        driver: "DriverAgent",
        rider: "RiderAgent | None",
        trip: Trip,
    ) -> None:
        """Record trip completion statistics for both driver and rider.

        Args:
            driver: The driver who completed the trip
            rider: The rider (if available)
            trip: The completed trip
        """
        fare = trip.fare or 0.0
        had_surge = trip.surge_multiplier > 1.0

        # Calculate timing
        pickup_time_seconds = 0.0
        wait_time_seconds = 0.0
        trip_duration_seconds = 0.0

        if trip.matched_at and trip.driver_arrived_at:
            pickup_time_seconds = (trip.driver_arrived_at - trip.matched_at).total_seconds()

        if trip.requested_at and trip.matched_at:
            wait_time_seconds = (trip.matched_at - trip.requested_at).total_seconds()

        if trip.started_at and trip.completed_at:
            trip_duration_seconds = (trip.completed_at - trip.started_at).total_seconds()

        # Record driver statistics
        driver.statistics.record_trip_completed(
            fare=fare,
            pickup_time_seconds=pickup_time_seconds,
            trip_duration_seconds=trip_duration_seconds,
        )

        # Record rider statistics
        if rider:
            rider.statistics.record_trip_completed(
                fare=fare,
                wait_time_seconds=wait_time_seconds,
                pickup_wait_seconds=pickup_time_seconds,
                had_surge=had_surge,
            )

    def cancel_trip(
        self,
        trip_id: str,
        cancelled_by: CancellationActor = "system",
        reason: str = "cancelled",
    ) -> None:
        """Cancel an active trip."""
        trip = self._active_trips.get(trip_id)
        if not trip:
            return

        driver = None
        rider = None

        # Update driver status if assigned
        if trip.driver_id:
            driver = self._drivers.get(trip.driver_id)
            if driver:
                driver.complete_trip()
                # Track cancellation in driver stats (if matched)
                driver.statistics.record_trip_cancelled()

        # Update rider status
        if self._registry_manager:
            rider = self._registry_manager.get_rider(trip.rider_id)
            if rider:
                rider.cancel_trip()
                # Track cancellation in rider stats
                rider.statistics.record_trip_cancelled()

        # Cancel the trip
        trip.cancel(by=cancelled_by, reason=reason, stage=trip.state.value)
        self._emit_trip_state_event(trip, "trip.cancelled")

        # Clean up pending offer candidates
        self._pending_offer_candidates.pop(trip_id, None)

        # Remove from active trips
        self.complete_trip(trip_id, trip)

    def _emit_trip_state_event(self, trip: Trip, event_type: TripEventType) -> None:
        """Emit a trip state change event."""
        if not self._kafka_producer:
            return

        event = EventFactory.create_for_trip(
            TripEvent,
            trip,
            update_causation=True,
            event_type=event_type,
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=trip.driver_id,
            pickup_location=trip.pickup_location,
            dropoff_location=trip.dropoff_location,
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            timestamp=self._format_timestamp(),
        )

        self._publish_trip_event(event, trip.trip_id)

    # --- Puppet Drive Control Methods ---

    def start_puppet_drive_to_pickup(
        self,
        driver_id: str,
        trip_id: str,
    ) -> tuple["RouteResponse", PuppetDriveController]:
        """Start a puppet driver driving to pickup location.

        Returns route info and the drive controller for monitoring.
        Raises ValueError if prerequisites not met.
        """
        driver = self._drivers.get(driver_id)
        if not driver:
            raise ValueError(f"Driver {driver_id} not found")

        if not getattr(driver, "_is_puppet", False):
            raise ValueError("Driver is not a puppet")

        trip = self._active_trips.get(trip_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        if driver.status != "en_route_pickup":
            raise ValueError(f"Driver must be in 'en_route_pickup' status, got '{driver.status}'")

        if not driver.location:
            raise ValueError(f"Driver {driver_id} has no location")

        # Stop any existing drive for this driver
        if driver_id in self._puppet_drives:
            self._puppet_drives[driver_id].stop()

        # Fetch route
        route = self._osrm_client.get_route_sync(driver.location, trip.pickup_location)

        # Store pickup route on trip for visualization
        trip.pickup_route = route.geometry

        # Create and start drive controller
        controller = PuppetDriveController(
            driver=driver,
            trip=trip,
            route_response=route,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            speed_multiplier=self._settings.simulation.speed_multiplier,
            is_pickup_drive=True,
            simulation_engine=self._simulation_engine,
        )

        self._puppet_drives[driver_id] = controller
        controller.start()

        return route, controller

    def start_puppet_drive_to_destination(
        self,
        driver_id: str,
        trip_id: str,
    ) -> tuple["RouteResponse", PuppetDriveController]:
        """Start a puppet driver driving to destination.

        Returns route info and the drive controller for monitoring.
        Raises ValueError if prerequisites not met.
        """
        driver = self._drivers.get(driver_id)
        if not driver:
            raise ValueError(f"Driver {driver_id} not found")

        if not getattr(driver, "_is_puppet", False):
            raise ValueError("Driver is not a puppet")

        trip = self._active_trips.get(trip_id)
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        if driver.status != "en_route_destination":
            raise ValueError(
                f"Driver must be in 'en_route_destination' status, got '{driver.status}'"
            )

        if not driver.location:
            raise ValueError(f"Driver {driver_id} has no location")

        # Stop any existing drive for this driver
        if driver_id in self._puppet_drives:
            self._puppet_drives[driver_id].stop()

        # Fetch route from driver's current location to dropoff
        route = self._osrm_client.get_route_sync(driver.location, trip.dropoff_location)

        # Store route on trip for visualization
        trip.route = route.geometry

        # Create and start drive controller
        controller = PuppetDriveController(
            driver=driver,
            trip=trip,
            route_response=route,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            speed_multiplier=self._settings.simulation.speed_multiplier,
            is_pickup_drive=False,
            simulation_engine=self._simulation_engine,
        )

        self._puppet_drives[driver_id] = controller
        controller.start()

        return route, controller

    def get_puppet_drive_status(self, driver_id: str) -> PuppetDriveStatus | None:
        """Get status of an active puppet drive."""
        controller = self._puppet_drives.get(driver_id)
        if not controller:
            return None

        return {
            "is_running": controller.is_running,
            "is_completed": controller.is_completed,
        }
