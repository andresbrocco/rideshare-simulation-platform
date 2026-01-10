"""Tests for notification dispatch system."""

from unittest.mock import Mock

import pytest

from matching.notification_dispatch import NotificationDispatch
from trip import Trip, TripState


@pytest.fixture
def mock_driver_agent():
    """Create mock driver agent."""
    agent = Mock()
    agent.driver_id = "driver-123"
    agent.receive_offer.return_value = True
    agent.current_rating = 4.8
    return agent


@pytest.fixture
def mock_rider_agent():
    """Create mock rider agent."""
    agent = Mock()
    agent.rider_id = "rider-456"
    agent.current_rating = 4.5
    return agent


@pytest.fixture
def mock_registry_manager(mock_driver_agent, mock_rider_agent):
    """Create mock registry manager with mock agents."""
    manager = Mock()
    manager.get_agent.side_effect = lambda agent_id: {
        "driver-123": mock_driver_agent,
        "rider-456": mock_rider_agent,
    }.get(agent_id)
    manager.get_driver.side_effect = lambda driver_id: (
        mock_driver_agent if driver_id == "driver-123" else None
    )
    manager.get_rider.side_effect = lambda rider_id: (
        mock_rider_agent if rider_id == "rider-456" else None
    )
    return manager


@pytest.fixture
def sample_trip():
    """Create sample trip."""
    return Trip(
        trip_id="trip-789",
        rider_id="rider-456",
        driver_id="driver-123",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5610, -46.6560),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
    )


@pytest.mark.asyncio
class TestNotificationDispatch:
    """Test NotificationDispatch class."""

    async def test_notification_dispatch_init(self, mock_registry_manager):
        """Creates NotificationDispatch with registry manager."""
        dispatcher = NotificationDispatch(mock_registry_manager)
        assert dispatcher is not None

    async def test_send_driver_offer(
        self, mock_registry_manager, sample_trip, mock_driver_agent
    ):
        """Sends offer to driver agent."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        # The new interface takes driver object directly, not driver_id
        decision = dispatcher.send_driver_offer(
            mock_driver_agent, sample_trip, eta_seconds=300
        )

        assert decision in [True, False]
        mock_driver_agent.receive_offer.assert_called_once()

    async def test_driver_accepts_offer(
        self, mock_registry_manager, sample_trip, mock_driver_agent
    ):
        """Driver accepts offer based on DNA."""
        mock_driver_agent.receive_offer.return_value = True
        dispatcher = NotificationDispatch(mock_registry_manager)

        decision = dispatcher.send_driver_offer(
            mock_driver_agent, sample_trip, eta_seconds=300
        )

        assert decision is True

    async def test_driver_rejects_offer(
        self, mock_registry_manager, sample_trip, mock_driver_agent
    ):
        """Driver rejects offer based on DNA."""
        mock_driver_agent.receive_offer.return_value = False
        dispatcher = NotificationDispatch(mock_registry_manager)

        decision = dispatcher.send_driver_offer(
            mock_driver_agent, sample_trip, eta_seconds=300
        )

        assert decision is False

    async def test_notify_rider_match_success(
        self, mock_registry_manager, sample_trip, mock_rider_agent
    ):
        """Notifies rider of successful match."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_rider_match("rider-456", sample_trip, "driver-123")

        mock_rider_agent.on_match_found.assert_called_once_with(
            sample_trip, "driver-123"
        )

    async def test_notify_rider_no_drivers(
        self, mock_registry_manager, mock_rider_agent
    ):
        """Notifies rider of no_drivers_available."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_rider_no_drivers("rider-456", "trip-789")

        mock_rider_agent.on_no_drivers_available.assert_called_once_with("trip-789")

    async def test_notify_trip_state_change(
        self, mock_registry_manager, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties of trip state change."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_state_change(
            sample_trip, TripState.DRIVER_EN_ROUTE
        )

        mock_rider_agent.on_driver_en_route.assert_called_once_with(sample_trip)

    async def test_notify_driver_arrival(
        self, mock_registry_manager, sample_trip, mock_rider_agent
    ):
        """Notifies rider when driver arrives."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.DRIVER_ARRIVED)

        mock_rider_agent.on_driver_arrived.assert_called_once_with(sample_trip)

    async def test_notify_trip_start(
        self, mock_registry_manager, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties when trip starts."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.STARTED)

        mock_rider_agent.on_trip_started.assert_called_once_with(sample_trip)
        mock_driver_agent.on_trip_started.assert_called_once_with(sample_trip)

    async def test_notify_trip_completion(
        self, mock_registry_manager, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties on completion."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.COMPLETED)

        mock_rider_agent.on_trip_completed.assert_called_once_with(sample_trip)
        mock_driver_agent.on_trip_completed.assert_called_once_with(sample_trip)

    async def test_notify_trip_cancellation(
        self, mock_registry_manager, sample_trip, mock_driver_agent
    ):
        """Notifies counterparty on cancellation."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_cancellation(sample_trip, "rider")

        mock_driver_agent.on_trip_cancelled.assert_called_once_with(sample_trip)

    async def test_notify_trip_cancellation_by_driver(
        self, mock_registry_manager, sample_trip, mock_rider_agent
    ):
        """Notifies rider when driver cancels."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        await dispatcher.notify_trip_cancellation(sample_trip, "driver")

        mock_rider_agent.on_trip_cancelled.assert_called_once_with(sample_trip)

    async def test_sync_dispatch(
        self, mock_registry_manager, sample_trip, mock_driver_agent
    ):
        """Dispatch send_driver_offer is now sync."""
        dispatcher = NotificationDispatch(mock_registry_manager)

        decision = dispatcher.send_driver_offer(
            mock_driver_agent, sample_trip, eta_seconds=300
        )

        assert isinstance(decision, bool)

    async def test_agent_not_found(
        self, mock_registry_manager, sample_trip, mock_rider_agent
    ):
        """Handles rider not in registry for trip."""
        # Create a trip with a non-existent rider
        trip_no_rider = Trip(
            trip_id="trip-999",
            rider_id="nonexistent-rider",
            driver_id="driver-123",
            pickup_location=(-23.5505, -46.6333),
            dropoff_location=(-23.5610, -46.6560),
            pickup_zone_id="zone-1",
            dropoff_zone_id="zone-2",
            surge_multiplier=1.2,
            fare=25.50,
        )
        dispatcher = NotificationDispatch(mock_registry_manager)
        mock_driver = Mock()
        mock_driver.receive_offer.return_value = True

        # This should still work but use default rating
        decision = dispatcher.send_driver_offer(
            mock_driver, trip_no_rider, eta_seconds=300
        )

        assert decision is True
        offer_arg = mock_driver.receive_offer.call_args[0][0]
        assert offer_arg["rider_rating"] == 5.0  # Default rating when rider not found
