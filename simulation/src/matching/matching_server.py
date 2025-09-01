"""Matching server that coordinates driver-rider matching."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import simpy

from matching.driver_geospatial_index import DriverGeospatialIndex
from trip import Trip, TripState
from trips.trip_executor import TripExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from geo.osrm_client import OSRMClient
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
    ):
        self._env = env
        self._driver_index = driver_index
        self._notification_dispatch = notification_dispatch
        self._osrm_client = osrm_client
        self._kafka_producer = kafka_producer
        self._registry_manager = registry_manager
        self._redis_publisher = redis_publisher
        self._surge_calculator = surge_calculator
        self._pending_offers: dict[str, dict] = {}
        self._drivers: dict[str, DriverAgent] = {}
        self._active_trips: dict[str, Trip] = {}
        # Queue for trips that need their TripExecutor started from SimPy thread
        self._pending_trip_executions: list[tuple[DriverAgent, Trip]] = []
        # Trip completion tracking
        self._completed_trips: list[Trip] = []
        self._cancelled_trips: list[Trip] = []

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

        return {
            "completed_count": len(completed),
            "cancelled_count": len(cancelled),
            "avg_fare": avg_fare,
            "avg_duration_minutes": avg_duration,
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

        logger.info(f"Finding nearby drivers for trip {trip.trip_id}")
        nearby_drivers = await self.find_nearby_drivers(pickup_location)
        logger.info(f"Found {len(nearby_drivers)} nearby drivers")
        if not nearby_drivers:
            logger.warning(f"No nearby drivers found for trip {trip.trip_id}")
            self._emit_no_drivers_event(trip.trip_id, rider_id)
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

        # Composite score: ETA 50%, rating 30%, acceptance 20%
        score = eta_normalized * 0.5 + rating_normalized * 0.3 + acceptance_normalized * 0.2
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
        trip.transition_to(TripState.OFFER_SENT)

        self._emit_offer_sent_event(trip, driver.driver_id, offer_sequence, eta_seconds)

        accepted = self._notification_dispatch.send_driver_offer(
            driver=driver,
            trip=trip,
            eta_seconds=eta_seconds,
        )

        return accepted

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
