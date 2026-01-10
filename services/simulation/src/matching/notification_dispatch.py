"""Notification dispatch system for agent communication."""

import logging
from typing import TYPE_CHECKING

from trip import Trip, TripState

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent
    from matching.agent_registry_manager import AgentRegistryManager

logger = logging.getLogger(__name__)


class NotificationDispatch:
    """Dispatches notifications to driver and rider agents."""

    def __init__(self, registry_manager: "AgentRegistryManager"):
        self._registry = registry_manager

    def send_driver_offer(
        self, driver: "DriverAgent", trip: Trip, eta_seconds: int
    ) -> bool:
        """Send offer to driver and return decision.

        Args:
            driver: The DriverAgent to send the offer to
            trip: The Trip being offered
            eta_seconds: Estimated time of arrival in seconds

        Returns:
            True if accepted, False otherwise
        """
        rider = self._registry.get_rider(trip.rider_id)
        rider_rating = rider.current_rating if rider else 5.0

        offer = {
            "trip_id": trip.trip_id,
            "surge_multiplier": trip.surge_multiplier,
            "rider_rating": rider_rating,
            "eta_seconds": eta_seconds,
        }

        return driver.receive_offer(offer)

    async def notify_rider_match(
        self, rider_id: str, trip: Trip, driver_id: str
    ) -> None:
        """Notify rider of successful match."""
        rider = self._registry.get_rider(rider_id)
        if not rider:
            logger.warning(f"Rider {rider_id} not found in registry")
            return

        rider.on_match_found(trip, driver_id)

    async def notify_rider_no_drivers(self, rider_id: str, trip_id: str) -> None:
        """Notify rider of no drivers available."""
        rider = self._registry.get_rider(rider_id)
        if not rider:
            logger.warning(f"Rider {rider_id} not found in registry")
            return

        rider.on_no_drivers_available(trip_id)

    async def notify_trip_state_change(self, trip: Trip, new_state: TripState) -> None:
        """Notify both parties of trip state change."""
        rider = self._registry.get_rider(trip.rider_id)
        driver = self._registry.get_driver(trip.driver_id) if trip.driver_id else None

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
            driver = (
                self._registry.get_driver(trip.driver_id) if trip.driver_id else None
            )
            if driver:
                driver.on_trip_cancelled(trip)

        elif cancelled_by == "driver":
            rider = self._registry.get_rider(trip.rider_id)
            if rider:
                rider.on_trip_cancelled(trip)
