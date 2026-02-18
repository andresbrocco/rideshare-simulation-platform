from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import simpy

from events.schemas import TripEvent

if TYPE_CHECKING:
    from engine import TimeManager
    from kafka.producer import KafkaProducer
    from trip import Trip


@dataclass
class PendingOffer:
    trip: "Trip"  # Store full trip object for event emission
    driver_id: str
    offer_sequence: int
    timeout_process: simpy.Process


class OfferTimeoutManager:
    """Manages offer timeouts using SimPy processes"""

    def __init__(
        self,
        env: simpy.Environment,
        kafka_producer: "KafkaProducer",
        timeout_seconds: int = 15,
    ) -> None:
        self.env = env
        self.kafka_producer = kafka_producer
        self.timeout_seconds = timeout_seconds
        self.pending_offers: dict[str, PendingOffer] = {}
        self._time_manager: TimeManager | None = None  # Set externally for simulated time

    def start_offer_timeout(self, trip: "Trip", driver_id: str, offer_sequence: int) -> None:
        process = self.env.process(self._timeout_process(trip.trip_id))
        pending_offer = PendingOffer(
            trip=trip,  # Store full trip object for event emission
            driver_id=driver_id,
            offer_sequence=offer_sequence,
            timeout_process=process,
        )
        self.pending_offers[trip.trip_id] = pending_offer

    def _timeout_process(self, trip_id: str) -> Generator[Any, Any]:
        try:
            yield self.env.timeout(self.timeout_seconds)

            if trip_id in self.pending_offers:
                pending_offer = self.pending_offers[trip_id]
                self._emit_expiration_event(pending_offer)
                del self.pending_offers[trip_id]
        except simpy.Interrupt:
            pass

    def _emit_expiration_event(self, pending_offer: PendingOffer) -> None:
        trip = pending_offer.trip
        event = TripEvent(
            event_type="trip.offer_expired",
            trip_id=trip.trip_id,
            rider_id=trip.rider_id,
            driver_id=pending_offer.driver_id,
            pickup_location=trip.pickup_location,
            dropoff_location=trip.dropoff_location,
            pickup_zone_id=trip.pickup_zone_id,
            dropoff_zone_id=trip.dropoff_zone_id,
            surge_multiplier=trip.surge_multiplier,
            fare=trip.fare,
            offer_sequence=pending_offer.offer_sequence,
            timestamp=(
                self._time_manager.format_timestamp()
                if self._time_manager
                else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            ),
        )
        self.kafka_producer.produce(
            topic="trips",  # Correct topic (was "trip.offer_expired")
            key=trip.trip_id,
            value=event.model_dump_json(),
        )

    def clear_offer(self, trip_id: str, reason: str) -> None:
        if trip_id in self.pending_offers:
            pending_offer = self.pending_offers[trip_id]
            if not pending_offer.timeout_process.triggered:
                pending_offer.timeout_process.interrupt()
            del self.pending_offers[trip_id]

    def invalidate_offer(self, trip_id: str) -> None:
        self.clear_offer(trip_id, "invalidated")
