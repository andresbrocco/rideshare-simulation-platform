"""Matching server that coordinates driver-rider matching."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import simpy

from matching.driver_geospatial_index import DriverGeospatialIndex
from trip import Trip, TripState

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from geo.osrm_client import OSRMClient
    from kafka.producer import KafkaProducer


class MatchingServer:
    """Coordinates driver-rider matching with composite scoring."""

    def __init__(
        self,
        env: simpy.Environment,
        driver_index: DriverGeospatialIndex,
        notification_dispatch: Any,
        osrm_client: "OSRMClient",
        kafka_producer: "KafkaProducer | None" = None,
    ):
        self._env = env
        self._driver_index = driver_index
        self._notification_dispatch = notification_dispatch
        self._osrm_client = osrm_client
        self._kafka_producer = kafka_producer
        self._pending_offers: dict[str, dict] = {}
        self._drivers: dict[str, DriverAgent] = {}

    def register_driver(self, driver: "DriverAgent") -> None:
        self._drivers[driver.driver_id] = driver

    def unregister_driver(self, driver_id: str) -> None:
        self._drivers.pop(driver_id, None)

    async def request_match(
        self,
        rider_id: str,
        pickup_location: tuple[float, float],
        dropoff_location: tuple[float, float],
        pickup_zone_id: str,
        dropoff_zone_id: str,
        surge_multiplier: float,
        fare: float,
    ) -> Trip | None:
        trip = Trip(
            trip_id=str(uuid4()),
            rider_id=rider_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
            requested_at=datetime.now(UTC),
        )

        nearby_drivers = await self.find_nearby_drivers(pickup_location)
        if not nearby_drivers:
            self._emit_no_drivers_event(trip.trip_id, rider_id)
            return None

        ranked_drivers = self.rank_drivers(nearby_drivers)

        result = self.send_offer_cycle(trip, ranked_drivers)
        return result

    async def find_nearby_drivers(
        self,
        pickup_location: tuple[float, float],
        max_eta_seconds: int = 900,
    ) -> list[tuple["DriverAgent", int]]:
        nearby = self._driver_index.find_nearest_drivers(
            pickup_location[0],
            pickup_location[1],
            radius_km=10.0,
            status_filter="online",
        )

        result = []
        for driver_id, _distance_km in nearby:
            driver = self._drivers.get(driver_id)
            if not driver or not driver.location:
                continue

            try:
                route = await self._osrm_client.get_route(driver.location, pickup_location)
                eta_seconds = int(route.duration_seconds)

                if eta_seconds <= max_eta_seconds:
                    result.append((driver, eta_seconds))
            except Exception:
                continue

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
        for attempts, (driver, eta_seconds, _score) in enumerate(ranked_drivers):
            if attempts >= max_attempts:
                break

            accepted = self.send_offer(driver, trip, trip.offer_sequence + 1, eta_seconds)

            if accepted:
                trip.driver_id = driver.driver_id
                trip.transition_to(TripState.MATCHED)
                trip.matched_at = datetime.now(UTC)
                self._emit_matched_event(trip)
                return trip

            # Transition to rejected for next offer
            trip.transition_to(TripState.OFFER_REJECTED)

        self._emit_no_drivers_event(trip.trip_id, trip.rider_id)
        return None

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
