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
    return agent


@pytest.fixture
def mock_rider_agent():
    """Create mock rider agent."""
    agent = Mock()
    agent.rider_id = "rider-456"
    return agent


@pytest.fixture
def agent_registry(mock_driver_agent, mock_rider_agent):
    """Create agent registry with mock agents."""
    return {
        "driver-123": mock_driver_agent,
        "rider-456": mock_rider_agent,
    }


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

    async def test_notification_dispatch_init(self, agent_registry):
        """Creates NotificationDispatch with agent registry."""
        dispatcher = NotificationDispatch(agent_registry)
        assert dispatcher is not None

    async def test_send_driver_offer(self, agent_registry, sample_trip, mock_driver_agent):
        """Sends offer to driver agent."""
        dispatcher = NotificationDispatch(agent_registry)

        decision = await dispatcher.send_driver_offer("driver-123", sample_trip)

        assert decision in ["accepted", "rejected"]
        mock_driver_agent.receive_offer.assert_called_once()

    async def test_driver_accepts_offer(self, agent_registry, sample_trip, mock_driver_agent):
        """Driver accepts offer based on DNA."""
        mock_driver_agent.receive_offer.return_value = True
        dispatcher = NotificationDispatch(agent_registry)

        decision = await dispatcher.send_driver_offer("driver-123", sample_trip)

        assert decision == "accepted"

    async def test_driver_rejects_offer(self, agent_registry, sample_trip, mock_driver_agent):
        """Driver rejects offer based on DNA."""
        mock_driver_agent.receive_offer.return_value = False
        dispatcher = NotificationDispatch(agent_registry)

        decision = await dispatcher.send_driver_offer("driver-123", sample_trip)

        assert decision == "rejected"

    async def test_notify_rider_match_success(self, agent_registry, sample_trip, mock_rider_agent):
        """Notifies rider of successful match."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_rider_match("rider-456", sample_trip, "driver-123")

        mock_rider_agent.on_match_found.assert_called_once_with(sample_trip, "driver-123")

    async def test_notify_rider_no_drivers(self, agent_registry, mock_rider_agent):
        """Notifies rider of no_drivers_available."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_rider_no_drivers("rider-456", "trip-789")

        mock_rider_agent.on_no_drivers_available.assert_called_once_with("trip-789")

    async def test_notify_trip_state_change(
        self, agent_registry, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties of trip state change."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.DRIVER_EN_ROUTE)

        mock_rider_agent.on_driver_en_route.assert_called_once_with(sample_trip)

    async def test_notify_driver_arrival(self, agent_registry, sample_trip, mock_rider_agent):
        """Notifies rider when driver arrives."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.DRIVER_ARRIVED)

        mock_rider_agent.on_driver_arrived.assert_called_once_with(sample_trip)

    async def test_notify_trip_start(
        self, agent_registry, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties when trip starts."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.STARTED)

        mock_rider_agent.on_trip_started.assert_called_once_with(sample_trip)
        mock_driver_agent.on_trip_started.assert_called_once_with(sample_trip)

    async def test_notify_trip_completion(
        self, agent_registry, sample_trip, mock_rider_agent, mock_driver_agent
    ):
        """Notifies both parties on completion."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_state_change(sample_trip, TripState.COMPLETED)

        mock_rider_agent.on_trip_completed.assert_called_once_with(sample_trip)
        mock_driver_agent.on_trip_completed.assert_called_once_with(sample_trip)

    async def test_notify_trip_cancellation(self, agent_registry, sample_trip, mock_driver_agent):
        """Notifies counterparty on cancellation."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_cancellation(sample_trip, "rider")

        mock_driver_agent.on_trip_cancelled.assert_called_once_with(sample_trip)

    async def test_notify_trip_cancellation_by_driver(
        self, agent_registry, sample_trip, mock_rider_agent
    ):
        """Notifies rider when driver cancels."""
        dispatcher = NotificationDispatch(agent_registry)

        await dispatcher.notify_trip_cancellation(sample_trip, "driver")

        mock_rider_agent.on_trip_cancelled.assert_called_once_with(sample_trip)

    async def test_async_dispatch(self, agent_registry, sample_trip):
        """Dispatch uses async/await pattern."""
        dispatcher = NotificationDispatch(agent_registry)

        decision = await dispatcher.send_driver_offer("driver-123", sample_trip)

        assert isinstance(decision, str)

    async def test_agent_not_found(self, agent_registry, sample_trip):
        """Handles agent not in registry."""
        dispatcher = NotificationDispatch(agent_registry)

        decision = await dispatcher.send_driver_offer("nonexistent-driver", sample_trip)

        assert decision == "rejected"
