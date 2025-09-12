"""Matching server that coordinates driver-rider matching."""

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import simpy

from matching.driver_geospatial_index import DriverGeospatialIndex
from puppet.drive_controller import PuppetDriveController
from settings import Settings
from trip import Trip, TripState
from trips.trip_executor import TripExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from engine.simulation_engine import SimulationEngine
    from geo.osrm_client import OSRMClient, RouteResponse
    from kafka.producer import KafkaProducer
    from matching.agent_registry_manager import AgentRegistryManager
    from matching.surge_pricing import SurgePricingCalculator
    from redis_client.publisher import RedisPublisher


class MatchingServer:
    """Coordinates driver-rider matching with composite scoring."""

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
        self._pending_offers: dict[str, dict] = {}
        # Store remaining candidates when puppet driver gets offer (for continuation after rejection)
        # Maps trip_id -> {"remaining_drivers": [...], "current_attempt": int, "max_attempts": int}
        self._pending_offer_candidates: dict[str, dict] = {}
        self._drivers: dict[str, DriverAgent] = {}
        self._active_trips: dict[str, Trip] = {}
        # Queue for trips that need their TripExecutor started from SimPy thread
        self._pending_trip_executions: list[tuple[DriverAgent, Trip]] = []
        # Trip completion tracking
        self._completed_trips: list[Trip] = []
        self._cancelled_trips: list[Trip] = []
        # Thread-safe driver reservation to prevent double-matching
        self._matching_lock = threading.Lock()
        self._reserved_drivers: set[str] = set()  # Drivers currently receiving offers
        # Matching outcome tracking
        self._offers_sent: int = 0
        self._offers_accepted: int = 0
        self._offers_rejected: int = 0
        self._offers_expired: int = 0
        # Puppet drive controllers (for background thread movement)
        self._puppet_drives: dict[str, PuppetDriveController] = {}

    def register_driver(self, driver: "DriverAgent") -> None:
        self._drivers[driver.driver_id] = driver

    def unregister_driver(self, driver_id: str) -> None:
        self._drivers.pop(driver_id, None)

    def get_active_trips(self) -> list[Trip]:
        """Get all active (non-completed/cancelled) trips."""
        return list(self._active_trips.values())

    def complete_trip(self, trip_id: str, trip: "Trip | None" = None) -> None:
        """Remove trip from active tracking and record completion/cancellation.

        Args:
            trip_id: The trip ID to complete
            trip: Optional trip object with final state for tracking
        """
        removed_trip = self._active_trips.pop(trip_id, None)

        # Use provided trip or the removed one for tracking
        tracking_trip = trip or removed_trip
        if tracking_trip:
            if tracking_trip.state.value == "cancelled":
                self._cancelled_trips.append(tracking_trip)
            elif tracking_trip.state.value == "completed":
                self._completed_trips.append(tracking_trip)

    def get_completed_trips(self) -> list["Trip"]:
        """Get all completed trips."""
        return self._completed_trips.copy()

    def get_cancelled_trips(self) -> list["Trip"]:
        """Get all cancelled trips."""
        return self._cancelled_trips.copy()

    def get_trip_stats(self) -> dict:
        """Get trip statistics for metrics."""
        completed = self._completed_trips
        cancelled = self._cancelled_trips

        total_fare = sum(t.fare for t in completed if t.fare)
        avg_fare = total_fare / len(completed) if completed else 0.0

        # Calculate average duration in minutes
        total_duration = 0.0
        duration_count = 0
        for t in completed:
            if t.matched_at and t.completed_at:
                duration = (t.completed_at - t.matched_at).total_seconds() / 60
                total_duration += duration
                duration_count += 1
        avg_duration = total_duration / duration_count if duration_count > 0 else 0.0

        # Calculate average wait time (request to match) in seconds
        total_wait = 0.0
        wait_count = 0
        for t in completed:
            if t.requested_at and t.matched_at:
                wait_seconds = (t.matched_at - t.requested_at).total_seconds()
                total_wait += wait_seconds
                wait_count += 1
        avg_wait_seconds = total_wait / wait_count if wait_count > 0 else 0.0

        # Calculate average pickup time (match to driver arrived) in seconds
        total_pickup = 0.0
        pickup_count = 0
        for t in completed:
            if t.matched_at and t.driver_arrived_at:
                pickup_seconds = (t.driver_arrived_at - t.matched_at).total_seconds()
                total_pickup += pickup_seconds
                pickup_count += 1
        avg_pickup_seconds = total_pickup / pickup_count if pickup_count > 0 else 0.0

        return {
            "completed_count": len(completed),
            "cancelled_count": len(cancelled),
            "avg_fare": avg_fare,
            "avg_duration_minutes": avg_duration,
            "avg_wait_seconds": avg_wait_seconds,
            "avg_pickup_seconds": avg_pickup_seconds,
        }

    def get_matching_stats(self) -> dict:
        """Get matching outcome statistics for metrics."""
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
            requested_at=datetime.now(UTC),
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
            self._emit_no_drivers_event(trip.trip_id, rider_id)
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
        logger.info(f"Searching for nearby drivers at {pickup_location}")
        logger.info(f"Driver index has {len(self._driver_index._driver_locations)} drivers total")
        logger.info(f"Drivers registered with matching server: {len(self._drivers)}")

        nearby = self._driver_index.find_nearest_drivers(
            pickup_location[0],
            pickup_location[1],
            radius_km=10.0,
            status_filter="online",
        )
        logger.info(f"Spatial index returned {len(nearby)} nearby online drivers")

        result = []
        for driver_id, _distance_km in nearby:
            logger.info(f"Processing driver {driver_id}, distance={_distance_km:.2f}km")
            driver = self._drivers.get(driver_id)
            if not driver or not driver.location:
                logger.warning(f"Driver {driver_id} not found or has no location")
                continue

            logger.info(f"Driver {driver_id} location: {driver.location}")
            try:
                route = await self._osrm_client.get_route(driver.location, pickup_location)
                eta_seconds = int(route.duration_seconds)
                logger.info(f"Driver {driver_id} ETA: {eta_seconds}s (max={max_eta_seconds}s)")

                if eta_seconds <= max_eta_seconds:
                    result.append((driver, eta_seconds))
                    logger.info(f"Driver {driver_id} added to result (ETA within limit)")
                else:
                    logger.info(f"Driver {driver_id} ETA too long, skipping")
            except Exception as e:
                logger.error(f"Failed to get route for driver {driver_id}: {e}")
                continue

        logger.info(f"Returning {len(result)} drivers with valid ETAs")
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

        scored = []
        for driver, eta in driver_eta_list:
            score = self._calculate_composite_score(
                eta_seconds=eta,
                rating=driver.current_rating,
                acceptance_rate=driver.dna.acceptance_rate,
                min_eta=min_eta,
                max_eta=max_eta,
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

        # Composite score using configurable weights
        weights = self._settings.matching
        score = (
            eta_normalized * weights.ranking_eta_weight
            + rating_normalized * weights.ranking_rating_weight
            + acceptance_normalized * weights.ranking_acceptance_weight
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
                trip.matched_at = datetime.now(UTC)
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
        self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
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
                trip.matched_at = datetime.now(UTC)
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
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Queueing trip execution for trip {trip.trip_id}")
        self._pending_trip_executions.append((driver, trip))

    def start_pending_trip_executions(self) -> None:
        """Start any pending trip executions. Must be called from SimPy thread.

        This is called from SimulationEngine.step() to safely start
        TripExecutor processes within the SimPy thread context.
        """
        import logging

        logger = logging.getLogger(__name__)
        if self._pending_trip_executions:
            logger.info(f"Starting {len(self._pending_trip_executions)} pending trip executions")
        while self._pending_trip_executions:
            driver, trip = self._pending_trip_executions.pop(0)
            logger.info(f"Starting TripExecutor for trip {trip.trip_id}")
            self._start_trip_execution_internal(driver, trip)

    def _start_trip_execution_internal(self, driver: "DriverAgent", trip: Trip) -> None:
        """Actually start the TripExecutor. Must be called from SimPy thread.

        Args:
            driver: The matched driver
            trip: The matched trip
        """
        print(f"DEBUG: _start_trip_execution_internal called for trip {trip.trip_id}", flush=True)
        if not self._registry_manager:
            print(f"DEBUG: No registry_manager for trip {trip.trip_id}", flush=True)
            return

        rider = self._registry_manager.get_rider(trip.rider_id)
        if not rider:
            print(f"DEBUG: Rider {trip.rider_id} not found for trip {trip.trip_id}", flush=True)
            return

        print(f"DEBUG: Creating TripExecutor for trip {trip.trip_id}", flush=True)
        executor = TripExecutor(
            env=self._env,
            driver=driver,
            rider=rider,
            trip=trip,
            osrm_client=self._osrm_client,
            kafka_producer=self._kafka_producer,
            redis_publisher=self._redis_publisher,
            matching_server=self,
            settings=self._settings,
            simulation_engine=self._simulation_engine,
        )

        # Start the trip execution as a SimPy process
        print(f"DEBUG: Starting SimPy process for trip {trip.trip_id}", flush=True)
        self._env.process(executor.execute())
        print(f"DEBUG: SimPy process started for trip {trip.trip_id}", flush=True)

    def send_offer(
        self,
        driver: "DriverAgent",
        trip: Trip,
        offer_sequence: int,
        eta_seconds: int,
    ) -> bool:
        driver_id = driver.driver_id

        # Atomic check-and-reserve to prevent double-matching
        with self._matching_lock:
            # Skip if driver already reserved or in a trip
            if driver_id in self._reserved_drivers:
                logger.warning(f"Driver {driver_id} already reserved, skipping")
                return False
            if driver.active_trip:
                logger.warning(f"Driver {driver_id} already has active trip, skipping")
                return False

            # Reserve this driver (prevents double-matching without changing status)
            self._reserved_drivers.add(driver_id)

        try:
            trip.transition_to(TripState.OFFER_SENT)
            self._offers_sent += 1
            # Track offer in driver's statistics
            driver.statistics.record_offer_received()
            self._emit_offer_sent_event(trip, driver_id, offer_sequence, eta_seconds)

            # For puppet drivers, store offer and wait for manual action via API
            if getattr(driver, "_is_puppet", False):
                rider = (
                    self._registry_manager.get_rider(trip.rider_id)
                    if self._registry_manager
                    else None
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
            accepted = self._notification_dispatch.send_driver_offer(
                driver=driver,
                trip=trip,
                eta_seconds=eta_seconds,
            )

            # Track acceptance/rejection (global and per-driver)
            if accepted:
                self._offers_accepted += 1
                driver.statistics.record_offer_accepted()
            else:
                self._offers_rejected += 1
                driver.statistics.record_offer_rejected()

            # Release reservation regardless of accept/reject outcome
            # For accepted: driver will be tracked via active_trip, not reservation
            # For rejected: driver goes back to available pool
            with self._matching_lock:
                self._reserved_drivers.discard(driver_id)
                if not accepted:
                    self._driver_index.update_driver_status(driver_id, "online")

            return accepted

        except Exception:
            # Release reservation on error
            with self._matching_lock:
                self._reserved_drivers.discard(driver_id)
                self._driver_index.update_driver_status(driver_id, "online")
            raise

    def _emit_offer_sent_event(
        self,
        trip: Trip,
        driver_id: str,
        offer_sequence: int,
        eta_seconds: int,
    ) -> None:
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": "trip.offer_sent",
            "trip_id": trip.trip_id,
            "rider_id": trip.rider_id,
            "driver_id": driver_id,
            "offer_sequence": offer_sequence,
            "eta_seconds": eta_seconds,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self._kafka_producer.produce(
            topic="trips",
            key=trip.trip_id,
            value=event,
        )

    def _emit_matched_event(self, trip: Trip) -> None:
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": "trip.matched",
            "trip_id": trip.trip_id,
            "rider_id": trip.rider_id,
            "driver_id": trip.driver_id,
            "offer_sequence": trip.offer_sequence,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self._kafka_producer.produce(
            topic="trips",
            key=trip.trip_id,
            value=event,
        )

    def _emit_no_drivers_event(self, trip_id: str, rider_id: str) -> None:
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": "no_drivers_available",
            "trip_id": trip_id,
            "rider_id": rider_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self._kafka_producer.produce(
            topic="trips",
            key=trip_id,
            value=event,
        )

    def clear(self) -> None:
        """Clear all matching server state for simulation reset."""
        # Stop any active puppet drives
        for controller in self._puppet_drives.values():
            controller.stop()
        self._puppet_drives.clear()

        self._active_trips.clear()
        self._completed_trips.clear()
        self._cancelled_trips.clear()
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

        # Clear the geospatial index
        if hasattr(self._driver_index, "clear"):
            self._driver_index.clear()

    # --- Puppet Agent Helper Methods ---

    def get_pending_offer_for_driver(self, driver_id: str) -> dict | None:
        """Get the pending trip offer for a specific driver."""
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
            with self._matching_lock:
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
        with self._matching_lock:
            self._reserved_drivers.discard(driver_id)

        # Update trip state
        driver.accept_trip(trip_id)
        driver.start_pickup()  # Transition to en_route_pickup
        trip.driver_id = driver_id
        trip.transition_to(TripState.MATCHED)
        trip.matched_at = datetime.now(UTC)
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
        with self._matching_lock:
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
                self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
                self._active_trips.pop(trip.trip_id, None)
        else:
            # No more candidates available
            logger.info(f"No remaining candidates for trip {trip_id} after puppet rejection")
            self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
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
        with self._matching_lock:
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
                self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
                self._active_trips.pop(trip.trip_id, None)
        else:
            # No more candidates available
            logger.info(f"No remaining candidates for trip {trip_id} after puppet timeout")
            self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
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
        trip.started_at = datetime.now(UTC)
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
        trip.completed_at = datetime.now(UTC)

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
        self, trip_id: str, cancelled_by: str = "system", reason: str = "cancelled"
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

    def _emit_trip_state_event(self, trip: Trip, event_type: str) -> None:
        """Emit a trip state change event."""
        if not self._kafka_producer:
            return

        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "trip_id": trip.trip_id,
            "rider_id": trip.rider_id,
            "driver_id": trip.driver_id,
            "pickup_location": trip.pickup_location,
            "dropoff_location": trip.dropoff_location,
            "timestamp": datetime.now(UTC).isoformat(),
            "state": trip.state.value,
        }

        self._kafka_producer.produce(
            topic="trips",
            key=trip.trip_id,
            value=event,
        )

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
            speed_multiplier=self._settings.speed_multiplier,
            is_pickup_drive=True,
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
            speed_multiplier=self._settings.speed_multiplier,
            is_pickup_drive=False,
        )

        self._puppet_drives[driver_id] = controller
        controller.start()

        return route, controller

    def get_puppet_drive_status(self, driver_id: str) -> dict | None:
        """Get status of an active puppet drive."""
        controller = self._puppet_drives.get(driver_id)
        if not controller:
            return None

        return {
            "is_running": controller.is_running,
            "is_completed": controller.is_completed,
        }
