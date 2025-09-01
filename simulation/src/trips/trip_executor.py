"""Trip execution coordinator managing the full trip lifecycle."""

import asyncio
import logging
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import simpy

# Note: asyncio is still used for Redis publishing, but OSRM calls now use synchronous requests
from events.schemas import GPSPingEvent, PaymentEvent, TripEvent
from trip import Trip, TripState

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
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
        wait_timeout: int = 300,
        rider_boards: bool = True,
        rider_cancels_mid_trip: bool = False,
    ):
        self._env = env
        self._driver = driver
        self._rider = rider
        self._trip = trip
        self._osrm_client = osrm_client
        self._kafka_producer = kafka_producer
        self._redis_publisher = redis_publisher
        self._matching_server = matching_server
        self._wait_timeout = wait_timeout
        self._rider_boards = rider_boards
        self._rider_cancels_mid_trip = rider_cancels_mid_trip

    def execute(self) -> Generator[simpy.Event]:
        """Execute the full trip flow."""
        print(f"DEBUG: TripExecutor.execute() started for trip {self._trip.trip_id}", flush=True)
        logger.info(f"TripExecutor.execute() started for trip {self._trip.trip_id}")
        try:
            logger.info(f"Trip {self._trip.trip_id}: Starting drive to pickup")
            yield from self._drive_to_pickup()

            if self._trip.state == TripState.CANCELLED:
                logger.info(f"Trip {self._trip.trip_id}: Cancelled during pickup drive")
                return

            logger.info(f"Trip {self._trip.trip_id}: Waiting for rider")
            yield from self._wait_for_rider()

            if self._trip.state == TripState.CANCELLED:
                logger.info(f"Trip {self._trip.trip_id}: Cancelled while waiting for rider")
                return

            logger.info(f"Trip {self._trip.trip_id}: Starting trip")
            yield from self._start_trip()

            logger.info(f"Trip {self._trip.trip_id}: Driving to destination")
            yield from self._drive_to_destination()

            if self._trip.state == TripState.CANCELLED:
                logger.info(f"Trip {self._trip.trip_id}: Cancelled during drive to destination")
                return

            logger.info(f"Trip {self._trip.trip_id}: Completing trip")
            yield from self._complete_trip()
            logger.info(f"Trip {self._trip.trip_id}: Trip completed successfully!")
        except Exception as e:
            logger.error(f"TripExecutor error for trip {self._trip.trip_id}: {e}", exc_info=True)

    def _drive_to_pickup(self) -> Generator[simpy.Event]:
        """Drive from current location to pickup."""
        logger.info(
            f"Trip {self._trip.trip_id}: _drive_to_pickup - transitioning to DRIVER_EN_ROUTE"
        )
        self._trip.transition_to(TripState.DRIVER_EN_ROUTE)
        self._driver.start_pickup()
        self._emit_trip_event("trip.driver_en_route")
        self._rider.on_driver_en_route(self._trip)

        logger.info(
            f"Trip {self._trip.trip_id}: Fetching route from {self._driver.location} to {self._trip.pickup_location}"
        )
        try:
            route = self._osrm_client.get_route_sync(
                self._driver.location, self._trip.pickup_location
            )
            logger.info(
                f"Trip {self._trip.trip_id}: Route fetched - duration={route.duration_seconds}s, distance={route.distance_meters}m"
            )
        except Exception as e:
            logger.error(f"Trip {self._trip.trip_id}: OSRM route fetch failed: {e}", exc_info=True)
            raise

        duration = route.duration_seconds
        logger.info(f"Trip {self._trip.trip_id}: Starting simulated drive to pickup ({duration}s)")
        yield from self._simulate_drive(route.geometry, duration)

    def _wait_for_rider(self) -> Generator[simpy.Event]:
        """Wait at pickup location for rider."""
        self._trip.transition_to(TripState.DRIVER_ARRIVED)
        self._driver.update_location(*self._trip.pickup_location)
        self._emit_trip_event("trip.driver_arrived")
        self._rider.on_driver_arrived(self._trip)

        if not self._rider_boards:
            yield self._env.timeout(self._wait_timeout)
            self._trip.cancel(by="driver", reason="no_show", stage="pickup")
            self._emit_trip_event("trip.cancelled")
            self._driver.complete_trip()
            self._rider.cancel_trip()
            # Remove from active trips tracking and record cancellation
            if self._matching_server:
                self._matching_server.complete_trip(self._trip.trip_id, self._trip)
            return

        yield self._env.timeout(30)

    def _start_trip(self) -> Generator[simpy.Event]:
        """Start trip when rider boards."""
        self._trip.transition_to(TripState.STARTED)
        self._driver.start_trip()
        self._rider.start_trip()
        self._emit_trip_event("trip.started")
        self._driver.on_trip_started(self._trip)
        self._rider.on_trip_started(self._trip)
        yield self._env.timeout(0)

    def _drive_to_destination(self) -> Generator[simpy.Event]:
        """Drive from pickup to destination."""
        route = self._osrm_client.get_route_sync(
            self._trip.pickup_location, self._trip.dropoff_location
        )

        duration = route.duration_seconds
        yield from self._simulate_drive(route.geometry, duration, check_rider_cancel=True)

    def _complete_trip(self) -> Generator[simpy.Event]:
        """Complete trip and emit events."""
        logger.info(f"Trip {self._trip.trip_id}: _complete_trip - transitioning to COMPLETED")
        self._trip.transition_to(TripState.COMPLETED)
        self._trip.completed_at = datetime.now(UTC)
        self._driver.update_location(*self._trip.dropoff_location)
        self._rider.update_location(*self._trip.dropoff_location)

        logger.info(f"Trip {self._trip.trip_id}: Emitting completion events")
        self._emit_trip_event("trip.completed")
        self._emit_payment_event()

        logger.info(f"Trip {self._trip.trip_id}: Updating driver and rider status")
        self._driver.complete_trip()
        self._rider.complete_trip()

        self._driver.on_trip_completed(self._trip)
        self._rider.on_trip_completed(self._trip)

        # Remove from active trips tracking and record completion
        if self._matching_server:
            logger.info(f"Trip {self._trip.trip_id}: Removing from active trips")
            self._matching_server.complete_trip(self._trip.trip_id, self._trip)

        logger.info(f"Trip {self._trip.trip_id}: Trip execution finished")
        yield self._env.timeout(0)

    def _simulate_drive(
        self, geometry: list[tuple[float, float]], duration: float, check_rider_cancel: bool = False
    ) -> Generator[simpy.Event]:
        """Simulate driving along route with GPS updates."""
        gps_interval = 30
        num_intervals = int(duration / gps_interval)
        time_per_interval = duration / max(num_intervals, 1)

        for i in range(num_intervals):
            if check_rider_cancel and self._rider_cancels_mid_trip and i == num_intervals // 2:
                self._trip.cancel(by="rider", reason="changed_mind", stage="in_transit")
                self._emit_trip_event("trip.cancelled")
                self._driver.complete_trip()
                self._rider.cancel_trip()
                # Remove from active trips tracking and record cancellation
                if self._matching_server:
                    self._matching_server.complete_trip(self._trip.trip_id, self._trip)
                return

            progress = (i + 1) / max(num_intervals, 1)
            idx = int(progress * (len(geometry) - 1))
            current_pos = geometry[min(idx, len(geometry) - 1)]

            self._driver.update_location(*current_pos)
            if self._trip.state == TripState.STARTED:
                self._rider.update_location(*current_pos)

            self._emit_gps_ping(self._driver.driver_id, "driver", current_pos)

            yield self._env.timeout(time_per_interval)

    def _emit_trip_event(self, event_type: str) -> None:
        """Emit trip state transition event to Kafka and Redis."""
        event = TripEvent(
            event_type=event_type,
            trip_id=self._trip.trip_id,
            timestamp=datetime.now(UTC).isoformat(),
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
        )

        # Emit to Kafka (source of truth for data pipelines)
        if self._kafka_producer:
            self._kafka_producer.produce(
                topic="trips",
                key=self._trip.trip_id,
                value=event,
            )

        # Emit to Redis for real-time frontend updates
        if self._redis_publisher:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self._redis_publisher.publish(
                            channel="trip-updates",
                            message=event.model_dump(mode="json"),
                        )
                    )
                else:
                    loop.run_until_complete(
                        self._redis_publisher.publish(
                            channel="trip-updates",
                            message=event.model_dump(mode="json"),
                        )
                    )
            except RuntimeError:
                asyncio.run(
                    self._redis_publisher.publish(
                        channel="trip-updates",
                        message=event.model_dump(mode="json"),
                    )
                )

    def _emit_payment_event(self) -> None:
        """Emit payment processed event."""
        if not self._kafka_producer:
            return

        event = PaymentEvent(
            payment_id=str(uuid4()),
            trip_id=self._trip.trip_id,
            timestamp=datetime.now(UTC).isoformat(),
            rider_id=self._trip.rider_id,
            driver_id=self._trip.driver_id,
            payment_method_type=self._rider.dna.payment_method_type,
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

    def _emit_gps_ping(
        self, entity_id: str, entity_type: str, location: tuple[float, float]
    ) -> None:
        """Emit GPS ping event."""
        if not self._kafka_producer:
            return

        event = GPSPingEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=datetime.now(UTC).isoformat(),
            location=location,
            heading=random.uniform(0, 360),
            speed=random.uniform(20, 60),
            accuracy=5.0,
            trip_id=self._trip.trip_id,
        )

        self._kafka_producer.produce(
            topic="gps-pings",
            key=entity_id,
            value=event,
        )
