"""Notification dispatch system for agent communication."""

import logging
from typing import Any

from trip import Trip, TripState

logger = logging.getLogger(__name__)


class NotificationDispatch:
    """Dispatches notifications to driver and rider agents."""

    def __init__(self, agent_registry: dict[str, Any]):
        self.agent_registry = agent_registry

    async def send_driver_offer(self, driver_id: str, trip: Trip) -> str:
        """Send offer to driver and return decision."""
        driver = self.agent_registry.get(driver_id)
        if not driver:
            logger.warning(f"Driver {driver_id} not found in registry")
            return "rejected"

        offer = {
            "trip_id": trip.trip_id,
            "surge_multiplier": trip.surge_multiplier,
            "rider_rating": 5.0,
        }

        accepted = driver.receive_offer(offer)
        return "accepted" if accepted else "rejected"

    async def notify_rider_match(self, rider_id: str, trip: Trip, driver_id: str) -> None:
        """Notify rider of successful match."""
        rider = self.agent_registry.get(rider_id)
        if not rider:
            logger.warning(f"Rider {rider_id} not found in registry")
            return

        rider.on_match_found(trip, driver_id)

    async def notify_rider_no_drivers(self, rider_id: str, trip_id: str) -> None:
        """Notify rider of no drivers available."""
        rider = self.agent_registry.get(rider_id)
        if not rider:
            logger.warning(f"Rider {rider_id} not found in registry")
            return

        rider.on_no_drivers_available(trip_id)

    async def notify_trip_state_change(self, trip: Trip, new_state: TripState) -> None:
        """Notify both parties of trip state change."""
        rider = self.agent_registry.get(trip.rider_id)
        driver = self.agent_registry.get(trip.driver_id) if trip.driver_id else None

        if new_state == TripState.DRIVER_EN_ROUTE:
            if rider:
                rider.on_driver_en_route(trip)

        elif new_state == TripState.DRIVER_ARRIVED:
            if rider:
                rider.on_driver_arrived(trip)

        elif new_state == TripState.STARTED:
            if rider:
                rider.on_trip_started(trip)
            if driver:
                driver.on_trip_started(trip)

        elif new_state == TripState.COMPLETED:
            if rider:
                rider.on_trip_completed(trip)
            if driver:
                driver.on_trip_completed(trip)

    async def notify_trip_cancellation(self, trip: Trip, cancelled_by: str) -> None:
        """Notify counterparty of trip cancellation."""
        if cancelled_by == "rider":
            driver = self.agent_registry.get(trip.driver_id) if trip.driver_id else None
            if driver:
                driver.on_trip_cancelled(trip)

        elif cancelled_by == "driver":
            rider = self.agent_registry.get(trip.rider_id)
            if rider:
                rider.on_trip_cancelled(trip)
