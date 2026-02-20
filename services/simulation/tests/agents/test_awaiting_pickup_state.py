"""Tests for the awaiting_pickup rider state introduced in Spec 02."""

from unittest.mock import Mock, patch

import pytest
import simpy

from src.agents.rider_agent import RiderAgent
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env() -> simpy.Environment:
    return simpy.Environment()


@pytest.fixture
def rider(
    simpy_env: simpy.Environment, dna_factory: DNAFactory, mock_kafka_producer: Mock
) -> RiderAgent:
    dna = dna_factory.rider_dna(patience_threshold=300)
    agent = RiderAgent(
        rider_id="rider_awp_001",
        dna=dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.56, -46.65)
    return agent


@pytest.mark.unit
class TestOnDriverEnRoute:
    def test_transitions_requesting_to_awaiting_pickup(self, rider: RiderAgent) -> None:
        rider.request_trip("trip_001")
        assert rider.status == "requesting"

        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)

        assert rider.status == "awaiting_pickup"

    def test_does_not_transition_from_idle(self, rider: RiderAgent) -> None:
        assert rider.status == "idle"
        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)
        # Should remain idle — only transitions from requesting
        assert rider.status == "idle"

    def test_does_not_transition_from_on_trip(self, rider: RiderAgent) -> None:
        rider.request_trip("trip_001")
        rider.start_trip()
        assert rider.status == "on_trip"

        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)
        # Already past requesting, must stay on_trip
        assert rider.status == "on_trip"


@pytest.mark.unit
class TestStartTripFromAwaitingPickup:
    def test_transitions_awaiting_pickup_to_on_trip(self, rider: RiderAgent) -> None:
        rider.request_trip("trip_001")
        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)
        assert rider.status == "awaiting_pickup"

        rider.start_trip()

        assert rider.status == "on_trip"


@pytest.mark.unit
class TestCancelTripFromAwaitingPickup:
    def test_cancel_from_awaiting_pickup_goes_to_idle(self, rider: RiderAgent) -> None:
        rider.request_trip("trip_001")
        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)
        assert rider.status == "awaiting_pickup"

        rider.cancel_trip()

        assert rider.status == "idle"
        assert rider.active_trip is None

    def test_cancel_clears_trip_state(self, rider: RiderAgent) -> None:
        rider.request_trip("trip_001")
        rider.update_trip_state("en_route_pickup")
        fake_trip = Mock()
        rider.on_driver_en_route(fake_trip)

        rider.cancel_trip()

        assert rider._trip_state_value is None


@pytest.mark.unit
class TestPatienceTimeoutDoesNotFireOnAwaitingPickup:
    def test_patience_timeout_does_not_cancel_awaiting_pickup(
        self, simpy_env: simpy.Environment, dna_factory: DNAFactory, mock_kafka_producer: Mock
    ) -> None:
        """Patience timeout loop must exit when rider reaches awaiting_pickup."""
        dna = dna_factory.rider_dna(
            avg_rides_per_week=100000,
            patience_threshold=120,  # minimum allowed by RiderDNA
        )
        agent = RiderAgent(
            rider_id="rider_awp_patience_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            immediate_first_trip=True,
        )
        agent.update_location(-23.56, -46.65)

        def simulate_driver_en_route() -> simpy.events.Event:
            # Wait until agent is in requesting state, then call on_driver_en_route
            yield simpy_env.timeout(5)
            if agent.status == "requesting":
                agent.on_driver_en_route(Mock())

        simpy_env.process(agent.run())
        simpy_env.process(simulate_driver_en_route())

        # Run well past patience_threshold — rider should NOT have been cancelled
        simpy_env.run(until=dna.patience_threshold + 20)

        # Rider must still be in awaiting_pickup (driver hasn't called start_trip)
        assert agent.status == "awaiting_pickup"

    def test_patience_timeout_still_fires_when_only_requesting(
        self, simpy_env: simpy.Environment, dna_factory: DNAFactory, mock_kafka_producer: Mock
    ) -> None:
        """When no driver comes, patience timeout cancels the trip and emits trip.cancelled."""
        import json

        dna = dna_factory.rider_dna(
            avg_rides_per_week=100000,
            patience_threshold=120,  # minimum allowed by RiderDNA
        )
        agent = RiderAgent(
            rider_id="rider_awp_patience_002",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            immediate_first_trip=True,
        )
        agent.update_location(-23.56, -46.65)

        simpy_env.process(agent.run())
        simpy_env.run(until=dna.patience_threshold + 10)

        # Patience timeout must have fired at least once — verify via trip.cancelled event
        cancelled_events = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "trips"
            and "trip.cancelled" in call.kwargs.get("value", "")
        ]
        assert len(cancelled_events) > 0, "Patience timeout must have cancelled the trip"

        # The cancellation reason must be patience_timeout (not awaiting_pickup path)
        event = json.loads(cancelled_events[0].kwargs["value"])
        assert event["cancellation_reason"] == "patience_timeout"


@pytest.mark.unit
class TestPuppetAcceptLeavesRiderInAwaitingPickup:
    """Test that process_puppet_accept() correctly calls on_driver_en_route."""

    def test_puppet_accept_calls_on_driver_en_route(self) -> None:
        from unittest.mock import MagicMock

        from src.matching.matching_server import MatchingServer
        from src.trip import Trip, TripState

        # Build a minimal matching server with mocked dependencies
        env = simpy.Environment()
        driver_index = MagicMock()
        osrm_client = MagicMock()
        notification_dispatch = MagicMock()
        registry_manager = MagicMock()

        server = MatchingServer(
            env=env,
            driver_index=driver_index,
            notification_dispatch=notification_dispatch,
            osrm_client=osrm_client,
            registry_manager=registry_manager,
        )

        # Create a fake trip in active_trips
        trip = Trip(
            trip_id="trip_puppet_001",
            rider_id="rider_puppet_001",
            pickup_location=(-23.56, -46.65),
            dropoff_location=(-23.55, -46.63),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=15.0,
        )
        trip.transition_to(TripState.OFFER_SENT)
        server._active_trips["trip_puppet_001"] = trip

        # Create a fake puppet driver
        driver = MagicMock()
        driver.driver_id = "driver_puppet_001"
        driver._is_puppet = True
        server._drivers["driver_puppet_001"] = driver
        server._reserved_drivers.add("driver_puppet_001")

        # Pending offer so process_puppet_accept doesn't return early
        server._pending_offers["driver_puppet_001"] = {
            "trip_id": "trip_puppet_001",
            "surge_multiplier": 1.0,
            "rider_rating": 5.0,
            "eta_seconds": 120,
        }

        # Mock rider
        rider = MagicMock()
        registry_manager.get_rider.return_value = rider

        server.process_puppet_accept("driver_puppet_001", "trip_puppet_001")

        # on_driver_en_route must have been called with the trip
        rider.on_driver_en_route.assert_called_once_with(trip)


@pytest.mark.unit
class TestApiRiderCountsIncludeAwaitingPickup:
    """Verify the simulation status response model includes riders_awaiting_pickup."""

    def test_simulation_status_response_has_awaiting_pickup_field(self) -> None:
        from src.api.models.simulation import SimulationStatusResponse

        response = SimulationStatusResponse(
            state="running",
            speed_multiplier=1,
            current_time="2026-01-01T00:00:00+00:00",
            drivers_total=10,
            drivers_offline=2,
            drivers_available=5,
            drivers_en_route_pickup=2,
            drivers_on_trip=1,
            riders_total=20,
            riders_idle=10,
            riders_requesting=5,
            riders_awaiting_pickup=3,
            riders_on_trip=2,
            active_trips_count=3,
            uptime_seconds=100.0,
        )

        assert response.riders_awaiting_pickup == 3

    def test_simulation_status_response_serialises_awaiting_pickup(self) -> None:
        from src.api.models.simulation import SimulationStatusResponse

        response = SimulationStatusResponse(
            state="running",
            speed_multiplier=1,
            current_time="2026-01-01T00:00:00+00:00",
            drivers_total=5,
            drivers_offline=0,
            drivers_available=2,
            drivers_en_route_pickup=2,
            drivers_on_trip=1,
            riders_total=10,
            riders_idle=4,
            riders_requesting=2,
            riders_awaiting_pickup=2,
            riders_on_trip=2,
            active_trips_count=2,
            uptime_seconds=60.0,
        )

        data = response.model_dump()
        assert "riders_awaiting_pickup" in data
        assert data["riders_awaiting_pickup"] == 2
