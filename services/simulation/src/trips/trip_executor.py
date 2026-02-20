"""Trip execution coordinator managing the full trip lifecycle."""

import logging
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import simpy

from agents.event_emitter import GPS_PING_INTERVAL_MOVING
from core.exceptions import PermanentError, TransientError
from events.factory import EventFactory
from events.schemas import PaymentEvent, TripEvent
from geo.distance import is_within_proximity
from geo.gps_simulation import precompute_headings
from geo.osrm_client import OSRMServiceError, RouteResponse
from settings import SimulationSettings
from trip import Trip, TripState

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from engine import SimulationEngine
    from geo.osrm_client import OSRMClient
    from kafka.producer import KafkaProducer
    from matching.matching_server import MatchingServer
    from redis_client.publisher import RedisPublisher


class TripExecutor:
    """Coordinates trip execution from match to completion."""

    def __init__(
        self,
        env: simpy.Environment,
        driver: "DriverAgent",
        rider: "RiderAgent",
        trip: Trip,
        osrm_client: "OSRMClient",
        kafka_producer: "KafkaProducer | None",
        redis_publisher: "RedisPublisher | None" = None,
        matching_server: "MatchingServer | None" = None,
        settings: SimulationSettings | None = None,
        wait_timeout: int = 300,
        rider_boards: bool = True,
        rider_cancels_mid_trip: bool = False,
        simulation_engine: "SimulationEngine | None" = None,
    ):
        self._env = env
        self._driver = driver
        self._rider = rider
        self._trip = trip
        self._osrm_client = osrm_client
        self._kafka_producer = kafka_producer
        self._redis_publisher = redis_publisher
        self._matching_server = matching_server
        self._settings = settings or SimulationSettings()
        self._wait_timeout = wait_timeout
        self._rider_boards = rider_boards
        self._rider_cancels_mid_trip = rider_cancels_mid_trip
        self._simulation_engine = simulation_engine

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

    def execute(self) -> Generator[simpy.Event]:
        """Execute the full trip flow."""
        logger.debug("TripExecutor.execute() started", extra={"trip_id": self._trip.trip_id})
        logger.info(f"TripExecutor.execute() started for trip {self._trip.trip_id}")
        try:
            logger.info(f"Trip {self._trip.trip_id}: Starting drive to pickup")
            yield from self._drive_to_pickup()

            if self._trip.state == TripState.CANCELLED:
                logger.info(f"Trip {self._trip.trip_id}: Cancelled during pickup drive")
                return

            logger.info(f"Trip {self._trip.trip_id}: Waiting for rider")
            yield from self._wait_for_rider()

            if self._trip.state == TripState.CANCELLED:  # type: ignore[comparison-overlap]
                logger.info(f"Trip {self._trip.trip_id}: Cancelled while waiting for rider")
                return

            logger.info(f"Trip {self._trip.trip_id}: Starting trip")
            yield from self._start_trip()

            logger.info(f"Trip {self._trip.trip_id}: Driving to destination")
            yield from self._drive_to_destination()

            if self._trip.state == TripState.CANCELLED:  # type: ignore[comparison-overlap]
                logger.info(f"Trip {self._trip.trip_id}: Cancelled during drive to destination")
                return

            logger.info(f"Trip {self._trip.trip_id}: Completing trip")
            yield from self._complete_trip()
            logger.info(f"Trip {self._trip.trip_id}: Trip completed successfully!")
        except PermanentError as e:
            # Non-retryable errors (validation, not found, etc.)
            self._cleanup_failed_trip(
                reason="permanent_error",
                stage=self._determine_current_stage(),
                error=e,
            )
        except TransientError as e:
            # Retryable errors (network, service unavailable)
            # Note: retries already handled in _get_route_with_retry
            self._cleanup_failed_trip(
                reason="transient_error",
                stage=self._determine_current_stage(),
                error=e,
            )
        except Exception as e:
            logger.exception(f"Unexpected error in trip {self._trip.trip_id}")
            self._cleanup_failed_trip(
                reason="unexpected_error",
                stage=self._determine_current_stage(),
                error=e,
            )

    def _drive_to_pickup(self) -> Generator[simpy.Event]:
        """Drive from current location to pickup."""
        logger.info(
            f"Trip {self._trip.trip_id}: _drive_to_pickup - transitioning to EN_ROUTE_PICKUP"
        )
        self._trip.transition_to(TripState.EN_ROUTE_PICKUP)
        self._driver.start_pickup()

        # Fetch route with retry logic
        driver_location = self._driver.location
        if driver_location is None:
            raise PermanentError(f"Driver location is None for trip {self._trip.trip_id}")
        logger.info(
            f"Trip {self._trip.trip_id}: Fetching route from {driver_location} to {self._trip.pickup_location}"
        )
        route = yield from self._get_route_with_retry(driver_location, self._trip.pickup_location)
        # Store pickup route for visualization
        self._trip.pickup_route = route.geometry
        logger.info(
            f"Trip {self._trip.trip_id}: Pickup route fetched - duration={route.duration_seconds}s, distance={route.distance_meters}m, points={len(route.geometry)}"
        )

        # DNA-based pre-pickup cancellation check
        eta_minutes = route.duration_seconds / 60.0
        distance_scaling = max(0.5, min(2.0, eta_minutes / 10.0))
        cancel_prob = self._driver.dna.cancellation_tendency * distance_scaling

        if random.random() < cancel_prob:
            logger.info(
                f"Trip {self._trip.trip_id}: Driver {self._driver.driver_id} cancelled pre-pickup "
                f"(tendency={self._driver.dna.cancellation_tendency:.3f}, "
                f"eta={route.duration_seconds:.0f}s, prob={cancel_prob:.3f})"
            )
            self._trip.cancel(by="driver", reason="driver_cancelled", stage="pickup")
            self._emit_trip_event("trip.cancelled")
            self._driver.complete_trip()
            self._rider.cancel_trip()
            self._driver.statistics.record_trip_cancelled()
            self._rider.statistics.record_trip_cancelled()
            if self._matching_server:
                self._matching_server.complete_trip(self._trip.trip_id, self._trip)
            return

        # Now emit event with pickup_route populated
        self._emit_trip_event("trip.en_route_pickup")
        self._rider.on_driver_en_route(self._trip)

        duration = route.duration_seconds
        logger.info(f"Trip {self._trip.trip_id}: Starting simulated drive to pickup ({duration}s)")
        yield from self._simulate_drive(
            geometry=route.geometry,
            duration=duration,
            destination=self._trip.pickup_location,
            check_proximity=True,
        )

    def _wait_for_rider(self) -> Generator[simpy.Event]:
        """Wait at pickup location for rider."""
        self._trip.transition_to(TripState.AT_PICKUP)
        self._trip.driver_arrived_at = self._current_time()
        self._driver.update_location(*self._trip.pickup_location)

        # Mark pickup route as complete for visualization
        # This ensures progress shows 100% even when arriving via proximity detection
        if self._trip.pickup_route:
            self._trip.pickup_route_progress_index = len(self._trip.pickup_route) - 1

        self._emit_trip_event("trip.at_pickup")
        self._rider.on_driver_arrived(self._trip)

        if not self._rider_boards:
            yield self._env.timeout(self._wait_timeout)
            self._trip.cancel(by="driver", reason="no_show", stage="pickup")
            self._emit_trip_event("trip.cancelled")
            self._driver.complete_trip()
            self._rider.cancel_trip()
            # Track cancellation stats
            self._driver.statistics.record_trip_cancelled()
            self._rider.statistics.record_trip_cancelled()
            # Remove from active trips tracking and record cancellation
            if self._matching_server:
                self._matching_server.complete_trip(self._trip.trip_id, self._trip)
            return

        yield self._env.timeout(30)

    def _start_trip(self) -> Generator[simpy.Event]:
        """Start trip when rider boards."""
        self._trip.transition_to(TripState.IN_TRANSIT)
        self._driver.start_trip()
        self._rider.start_trip()
        self._emit_trip_event("trip.in_transit")
        self._driver.on_trip_started(self._trip)
        self._rider.on_trip_started(self._trip)
        yield self._env.timeout(0)

    def _drive_to_destination(self) -> Generator[simpy.Event]:
        """Drive from pickup to destination."""
        route = yield from self._get_route_with_retry(
            self._trip.pickup_location, self._trip.dropoff_location
        )

        # Store route on trip for visualization
        self._trip.route = route.geometry

        duration = route.duration_seconds

        # Probabilistic mid-trip cancellation (only if test flag is not set)
        probabilistic_cancel_interval: int | None = None
        if (
            not self._rider_cancels_mid_trip
            and self._settings.mid_trip_cancellation_rate > 0
            and random.random() < self._settings.mid_trip_cancellation_rate
        ):
            gps_interval = GPS_PING_INTERVAL_MOVING
            num_intervals = int(duration / gps_interval)
            if num_intervals > 1:
                # Pick a random interval in the second half of the drive
                probabilistic_cancel_interval = random.randint(
                    num_intervals // 2, num_intervals - 1
                )

        yield from self._simulate_drive(
            geometry=route.geometry,
            duration=duration,
            destination=self._trip.dropoff_location,
            check_proximity=True,
            check_rider_cancel=True,
            probabilistic_cancel_interval=probabilistic_cancel_interval,
        )

    def _complete_trip(self) -> Generator[simpy.Event]:
        """Complete trip and emit events."""
        logger.info(f"Trip {self._trip.trip_id}: _complete_trip - transitioning to COMPLETED")
        self._trip.transition_to(TripState.COMPLETED)
        self._trip.completed_at = self._current_time()
        self._driver.update_location(*self._trip.dropoff_location)
        self._rider.update_location(*self._trip.dropoff_location)

        logger.info(f"Trip {self._trip.trip_id}: Emitting completion events")
        self._emit_trip_event("trip.completed")
        self._emit_payment_event()

        logger.info(f"Trip {self._trip.trip_id}: Updating driver and rider status")
        self._driver.complete_trip()
        self._rider.complete_trip()

        # Record trip completion statistics
        self._record_completion_stats()

        # Submit ratings from both parties
        self._submit_ratings()

        self._driver.on_trip_completed(self._trip)
        self._rider.on_trip_completed(self._trip)

        # Remove from active trips tracking and record completion
        if self._matching_server:
            logger.info(f"Trip {self._trip.trip_id}: Removing from active trips")
            self._matching_server.complete_trip(self._trip.trip_id, self._trip)

        logger.info(f"Trip {self._trip.trip_id}: Trip execution finished")
        yield self._env.timeout(0)

    def _submit_ratings(self) -> None:
        """Submit ratings from both driver and rider after trip completion."""
        # Rider rates driver (based on driver's service_quality DNA)
        rider_rating = self._rider.submit_rating_for_trip(self._trip, self._driver)
        if rider_rating is not None:
            logger.debug(f"Trip {self._trip.trip_id}: Rider submitted rating {rider_rating}")

        # Driver rates rider (based on rider's behavior_factor DNA)
        driver_rating = self._driver.submit_rating_for_trip(self._trip, self._rider)
        if driver_rating is not None:
            logger.debug(f"Trip {self._trip.trip_id}: Driver submitted rating {driver_rating}")

    def _record_completion_stats(self) -> None:
        """Record trip completion statistics for driver and rider."""
        fare = self._trip.fare or 0.0
        had_surge = self._trip.surge_multiplier > 1.0

        # Calculate timing
        pickup_time_seconds = 0.0
        wait_time_seconds = 0.0
        trip_duration_seconds = 0.0

        if self._trip.matched_at and self._trip.driver_arrived_at:
            pickup_time_seconds = (
                self._trip.driver_arrived_at - self._trip.matched_at
            ).total_seconds()

        if self._trip.requested_at and self._trip.matched_at:
            wait_time_seconds = (self._trip.matched_at - self._trip.requested_at).total_seconds()

        if self._trip.started_at and self._trip.completed_at:
            trip_duration_seconds = (
                self._trip.completed_at - self._trip.started_at
            ).total_seconds()

        # Record driver statistics
        self._driver.statistics.record_trip_completed(
            fare=fare,
            pickup_time_seconds=pickup_time_seconds,
            trip_duration_seconds=trip_duration_seconds,
        )

        # Record rider statistics
        self._rider.statistics.record_trip_completed(
            fare=fare,
            wait_time_seconds=wait_time_seconds,
            pickup_wait_seconds=pickup_time_seconds,
            had_surge=had_surge,
        )

    def _get_route_with_retry(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> Generator[simpy.Event, None, RouteResponse]:
        """Get route with exponential backoff retry logic."""
        max_attempts = self._settings.osrm_max_retries + 1
        base_delay = self._settings.osrm_retry_base_delay
        multiplier = self._settings.osrm_retry_multiplier

        for attempt in range(max_attempts):
            try:
                return self._osrm_client.get_route_sync(origin, destination)
            except PermanentError:
                raise  # Non-retryable (e.g., NoRouteFoundError)
            except TransientError as e:
                # Retryable (e.g., OSRMTimeoutError, OSRMServiceError)
                if attempt == max_attempts - 1:
                    raise
                delay = base_delay * (multiplier**attempt)
                logger.warning(
                    f"Trip {self._trip.trip_id}: OSRM failed (attempt {attempt + 1}/{max_attempts}), "
                    f"retrying in {delay}s: {e}"
                )
                yield self._env.timeout(delay)

        # Should never reach here, but satisfy type checker
        raise OSRMServiceError("Max retries exceeded")

    def _determine_current_stage(self) -> str:
        """Determine current trip stage based on state."""
        state_to_stage = {
            TripState.REQUESTED: "requested",
            TripState.OFFER_SENT: "matching",
            TripState.DRIVER_ASSIGNED: "matched",
            TripState.EN_ROUTE_PICKUP: "pickup",
            TripState.AT_PICKUP: "pickup",
            TripState.IN_TRANSIT: "in_transit",
        }
        return state_to_stage.get(self._trip.state, "unknown")

    def _cleanup_failed_trip(
        self,
        reason: str,
        stage: str,
        error: Exception | None = None,
    ) -> None:
        """Clean up trip state after unrecoverable failure."""
        logger.error(
            f"Trip {self._trip.trip_id}: Cleaning up failed trip - reason={reason}, stage={stage}"
        )

        # Cancel trip if not already terminal
        if self._trip.state not in {TripState.COMPLETED, TripState.CANCELLED}:
            self._trip.cancel(by="system", reason=reason, stage=stage)
            self._emit_trip_event("trip.cancelled")

        # Release driver back to online
        if self._driver.status != "offline":
            self._driver.complete_trip()

        # Release rider back to idle
        if self._rider.status != "idle":
            self._rider.cancel_trip()

        # Record failure statistics
        self._driver.statistics.record_trip_cancelled()
        self._rider.statistics.record_trip_cancelled()

        # Clean up matching server
        if self._matching_server:
            self._matching_server.complete_trip(self._trip.trip_id, self._trip)

    def _simulate_drive(
        self,
        geometry: list[tuple[float, float]],
        duration: float,
        destination: tuple[float, float] | None = None,
        check_proximity: bool = False,
        check_rider_cancel: bool = False,
        probabilistic_cancel_interval: int | None = None,
    ) -> Generator[simpy.Event]:
        """Simulate driving along route with GPS updates and optional proximity detection.

        Args:
            geometry: List of (lat, lon) coordinates representing the route
            duration: Expected duration in seconds from OSRM
            destination: Optional (lat, lon) for proximity-based arrival detection
            check_proximity: If True, check distance to destination at each update
            check_rider_cancel: If True, handle mid-trip rider cancellation

        Yields:
            SimPy timeout events for each GPS interval

        Note:
            When check_proximity is True and the driver is within the configured
            arrival_proximity_threshold_m of the destination, the drive ends early.
            This enables GPS-based arrival detection rather than purely time-based.
        """
        gps_interval = GPS_PING_INTERVAL_MOVING
        num_intervals = int(duration / gps_interval)
        time_per_interval = duration / max(num_intervals, 1)
        proximity_threshold = self._settings.arrival_proximity_threshold_m
        route_headings = precompute_headings(geometry)

        for i in range(num_intervals):
            if check_rider_cancel and self._rider_cancels_mid_trip and i == num_intervals // 2:
                self._trip.cancel(by="rider", reason="changed_mind", stage="in_transit")
                self._emit_trip_event("trip.cancelled")
                self._driver.complete_trip()
                self._rider.cancel_trip()
                # Track cancellation stats
                self._driver.statistics.record_trip_cancelled()
                self._rider.statistics.record_trip_cancelled()
                # Remove from active trips tracking and record cancellation
                if self._matching_server:
                    self._matching_server.complete_trip(self._trip.trip_id, self._trip)
                return

            if probabilistic_cancel_interval is not None and i == probabilistic_cancel_interval:
                logger.info(
                    f"Trip {self._trip.trip_id}: Rider cancelled mid-trip "
                    f"(probabilistic at interval {i}/{num_intervals})"
                )
                self._trip.cancel(by="rider", reason="changed_mind", stage="in_transit")
                self._emit_trip_event("trip.cancelled")
                self._driver.complete_trip()
                self._rider.cancel_trip()
                self._driver.statistics.record_trip_cancelled()
                self._rider.statistics.record_trip_cancelled()
                if self._matching_server:
                    self._matching_server.complete_trip(self._trip.trip_id, self._trip)
                return

            progress = (i + 1) / max(num_intervals, 1)
            idx = int(progress * (len(geometry) - 1))
            current_pos = geometry[min(idx, len(geometry) - 1)]

            # Look up precomputed heading for this segment
            if idx < len(route_headings):
                route_heading = route_headings[idx]
            else:
                # At end of route, preserve last heading
                route_heading = self._driver.heading

            # Track route progress and propagate to agents for their own GPS loops
            if self._trip.state == TripState.IN_TRANSIT:
                self._trip.route_progress_index = idx
                self._driver.update_route_progress(route_progress_index=idx)
                self._rider.update_trip_state(self._trip.state.value)
            elif self._trip.state == TripState.EN_ROUTE_PICKUP:
                self._trip.pickup_route_progress_index = idx
                self._driver.update_route_progress(pickup_route_progress_index=idx)

            self._driver.update_location(*current_pos, heading=route_heading)
            if self._trip.state == TripState.IN_TRANSIT:
                self._rider.update_location(*current_pos)

            # GPS-based proximity detection for arrival
            if (
                check_proximity
                and destination
                and is_within_proximity(
                    current_pos[0],
                    current_pos[1],
                    destination[0],
                    destination[1],
                    proximity_threshold,
                )
            ):
                logger.info(
                    f"Trip {self._trip.trip_id}: Arrived early via proximity detection "
                    f"(within {proximity_threshold}m of destination)"
                )
                return  # Exit early - arrived via proximity

            yield self._env.timeout(time_per_interval)

    def _emit_trip_event(
        self,
        event_type: Literal[
            "trip.requested",
            "trip.offer_sent",
            "trip.driver_assigned",
            "trip.en_route_pickup",
            "trip.at_pickup",
            "trip.in_transit",
            "trip.completed",
            "trip.cancelled",
            "trip.offer_expired",
            "trip.offer_rejected",
        ],
    ) -> None:
        """Emit trip state transition event to Kafka and Redis."""
        event = EventFactory.create_for_trip(
            TripEvent,
            self._trip,
            update_causation=True,
            event_type=event_type,
            trip_id=self._trip.trip_id,
            timestamp=self._format_timestamp(),
            rider_id=self._trip.rider_id,
            driver_id=self._trip.driver_id,
            pickup_location=self._trip.pickup_location,
            dropoff_location=self._trip.dropoff_location,
            pickup_zone_id=self._trip.pickup_zone_id,
            dropoff_zone_id=self._trip.dropoff_zone_id,
            surge_multiplier=self._trip.surge_multiplier,
            fare=self._trip.fare,
            cancelled_by=self._trip.cancelled_by,
            cancellation_reason=self._trip.cancellation_reason,
            cancellation_stage=self._trip.cancellation_stage,
            route=self._trip.route,
            pickup_route=self._trip.pickup_route,
            route_progress_index=self._trip.route_progress_index,
            pickup_route_progress_index=self._trip.pickup_route_progress_index,
        )

        # Emit to Kafka (source of truth for data pipelines)
        if self._kafka_producer:
            self._kafka_producer.produce(
                topic="trips",
                key=self._trip.trip_id,
                value=event,
            )

    def _emit_payment_event(self) -> None:
        """Emit payment processed event."""
        if not self._kafka_producer:
            return

        # Ensure driver_id is set for completed payments
        driver_id = self._trip.driver_id
        if driver_id is None:
            logger.warning(f"Trip {self._trip.trip_id} completed but driver_id is None")
            return

        payment_method = self._rider.dna.payment_method_type
        if payment_method not in ("credit_card", "digital_wallet"):
            payment_method = "credit_card"  # Default fallback

        # Payment is a leaf event (doesn't update causation chain)
        event = EventFactory.create_for_trip(
            PaymentEvent,
            self._trip,
            update_causation=False,
            payment_id=str(uuid4()),
            trip_id=self._trip.trip_id,
            timestamp=self._format_timestamp(),
            rider_id=self._trip.rider_id,
            driver_id=driver_id,
            payment_method_type=payment_method,
            payment_method_masked=self._rider.dna.payment_method_masked,
            fare_amount=self._trip.fare,
            platform_fee_percentage=0.25,
            platform_fee_amount=self._trip.fare * 0.25,
            driver_payout_amount=self._trip.fare * 0.75,
        )

        self._kafka_producer.produce(
            topic="payments",
            key=self._trip.trip_id,
            value=event,
        )
