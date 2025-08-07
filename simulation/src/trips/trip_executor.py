"""Trip execution coordinator managing the full trip lifecycle."""

import asyncio
import random
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import simpy

from events.schemas import GPSPingEvent, PaymentEvent, TripEvent
from trip import Trip, TripState

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from agents.rider_agent import RiderAgent
    from geo.osrm_client import OSRMClient
    from kafka.producer import KafkaProducer


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
        self._wait_timeout = wait_timeout
        self._rider_boards = rider_boards
        self._rider_cancels_mid_trip = rider_cancels_mid_trip

    def execute(self) -> Generator[simpy.Event]:
        """Execute the full trip flow."""
        yield from self._drive_to_pickup()

        if self._trip.state == TripState.CANCELLED:
            return

        yield from self._wait_for_rider()

        if self._trip.state == TripState.CANCELLED:
            return

        yield from self._start_trip()

        yield from self._drive_to_destination()

        if self._trip.state == TripState.CANCELLED:
            return

        yield from self._complete_trip()

    def _drive_to_pickup(self) -> Generator[simpy.Event]:
        """Drive from current location to pickup."""
        self._trip.transition_to(TripState.DRIVER_EN_ROUTE)
        self._driver.start_pickup()
        self._emit_trip_event("trip.driver_en_route")
        self._rider.on_driver_en_route(self._trip)

        route = asyncio.run(
            self._osrm_client.get_route(self._driver.location, self._trip.pickup_location)
        )

        duration = route.duration_seconds
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
        route = asyncio.run(
            self._osrm_client.get_route(self._trip.pickup_location, self._trip.dropoff_location)
        )

        duration = route.duration_seconds
        yield from self._simulate_drive(route.geometry, duration, check_rider_cancel=True)

    def _complete_trip(self) -> Generator[simpy.Event]:
        """Complete trip and emit events."""
        self._trip.transition_to(TripState.COMPLETED)
        self._driver.update_location(*self._trip.dropoff_location)
        self._rider.update_location(*self._trip.dropoff_location)

        self._emit_trip_event("trip.completed")
        self._emit_payment_event()

        self._driver.complete_trip()
        self._rider.complete_trip()

        self._driver.on_trip_completed(self._trip)
        self._rider.on_trip_completed(self._trip)

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
        """Emit trip state transition event."""
        if not self._kafka_producer:
            return

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

        self._kafka_producer.produce(
            topic="trips",
            key=self._trip.trip_id,
            value=event,
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
