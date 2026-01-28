"""Tests for GPS-based proximity arrival detection in trip execution."""

from unittest.mock import Mock

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.geo.osrm_client import RouteResponse
from src.settings import SimulationSettings
from src.trip import Trip, TripState
from src.trips.trip_executor import TripExecutor
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def driver_dna(dna_factory: DNAFactory):
    return dna_factory.driver_dna(acceptance_rate=0.9)


@pytest.fixture
def rider_dna(dna_factory: DNAFactory):
    return dna_factory.rider_dna()


@pytest.fixture
def driver_agent(simpy_env, driver_dna, mock_kafka_producer):
    agent = DriverAgent(
        driver_id="driver_proximity_001",
        dna=driver_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.55, -46.63)
    agent.go_online()
    return agent


@pytest.fixture
def rider_agent(simpy_env, rider_dna, mock_kafka_producer):
    agent = RiderAgent(
        rider_id="rider_proximity_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.54, -46.62)
    return agent


@pytest.fixture
def proximity_settings():
    """Settings configured for proximity testing with small threshold."""
    return SimulationSettings(
        arrival_proximity_threshold_m=50.0,
        arrival_timeout_multiplier=2.0,
    )


@pytest.fixture
def trip_with_close_pickup():
    """Trip where pickup is close to starting position."""
    return Trip(
        trip_id="trip_proximity_001",
        rider_id="rider_proximity_001",
        driver_id="driver_proximity_001",
        state=TripState.MATCHED,
        # Pickup very close to driver starting position (-23.55, -46.63)
        # About 30m away
        pickup_location=(-23.55027, -46.63),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone_1",
        dropoff_zone_id="zone_2",
        surge_multiplier=1.0,
        fare=25.50,
    )


@pytest.fixture
def trip_with_far_pickup():
    """Trip where pickup is far from starting position."""
    return Trip(
        trip_id="trip_proximity_002",
        rider_id="rider_proximity_001",
        driver_id="driver_proximity_001",
        state=TripState.MATCHED,
        # Pickup far from driver starting position (-23.55, -46.63)
        # About 2km away
        pickup_location=(-23.54, -46.62),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone_1",
        dropoff_zone_id="zone_2",
        surge_multiplier=1.0,
        fare=25.50,
    )


@pytest.fixture
def mock_osrm_client_for_proximity():
    """OSRM client that returns routes with detailed geometry for proximity testing."""
    client = Mock()

    def mock_get_route_sync(origin, destination):
        """Generate route with detailed geometry going through intermediate points."""
        # Create a geometry that interpolates between origin and destination
        # with many intermediate points for realistic GPS simulation
        num_points = 21  # 600 seconds / 30 second intervals = 20 intervals + 1
        geometry = []
        for i in range(num_points):
            progress = i / (num_points - 1)
            lat = origin[0] + (destination[0] - origin[0]) * progress
            lon = origin[1] + (destination[1] - origin[1]) * progress
            geometry.append((lat, lon))

        return RouteResponse(
            distance_meters=5000.0,
            duration_seconds=600.0,  # 10 minutes
            geometry=geometry,
            osrm_code="Ok",
        )

    client.get_route_sync = Mock(side_effect=mock_get_route_sync)
    return client


class TestProximityArrivalDetection:
    """Tests for GPS-based proximity arrival detection."""

    def test_trip_completes_with_proximity_detection(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test that trip completes successfully with proximity detection enabled."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip_with_far_pickup.state == TripState.COMPLETED
        assert driver_agent.status == "online"
        assert rider_agent.status == "offline"

    def test_proximity_detection_emits_correct_events(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test that all expected trip events are emitted."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        event_types = [
            (
                evt.get("event_type")
                if isinstance(evt, dict)
                else getattr(evt, "event_type", None)
            )
            for evt in events
        ]

        # All expected events should be present
        assert "trip.driver_en_route" in event_types
        assert "trip.driver_arrived" in event_types
        assert "trip.started" in event_types
        assert "trip.completed" in event_types

    def test_settings_threshold_is_used(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
    ):
        """Test that custom settings threshold is respected."""
        # Use max allowed threshold (500m) - still larger than default 50m
        settings = SimulationSettings(
            arrival_proximity_threshold_m=500.0,  # Max allowed threshold
            arrival_timeout_multiplier=2.0,
        )

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=settings,
        )

        # Verify the settings are used
        assert executor._settings.arrival_proximity_threshold_m == 500.0

        start_time = simpy_env.now
        process = simpy_env.process(executor.execute())
        simpy_env.run(process)
        elapsed = simpy_env.now - start_time

        # Trip should complete successfully
        assert trip_with_far_pickup.state == TripState.COMPLETED
        # Trip should take some simulated time
        assert elapsed > 0

    def test_default_settings_when_none_provided(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
    ):
        """Test that default settings are used when none provided."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=None,  # Explicitly None
        )

        # Should use default threshold of 50m
        assert executor._settings.arrival_proximity_threshold_m == 50.0

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip_with_far_pickup.state == TripState.COMPLETED


class TestProximityWithCancellation:
    """Tests for proximity detection interaction with cancellation scenarios."""

    def test_proximity_with_rider_no_show(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test proximity detection works correctly when rider doesn't board."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
            wait_timeout=10,  # Short timeout
            rider_boards=False,  # Rider doesn't board
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip_with_far_pickup.state == TripState.CANCELLED
        assert trip_with_far_pickup.cancelled_by == "driver"
        assert trip_with_far_pickup.cancellation_reason == "no_show"

    def test_proximity_with_mid_trip_cancellation(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test proximity detection works correctly with mid-trip rider cancellation."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
            rider_cancels_mid_trip=True,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip_with_far_pickup.state == TripState.CANCELLED
        assert trip_with_far_pickup.cancelled_by == "rider"
        assert trip_with_far_pickup.cancellation_reason == "changed_mind"


class TestProximityGPSUpdates:
    """Tests for GPS updates during proximity-enabled trips."""

    def test_gps_pings_emitted_during_proximity_trip(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test that GPS pings are emitted during trip with proximity detection."""
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]

        # Should have GPS pings from both phases
        assert len(gps_calls) > 0

    def test_driver_location_updates_toward_destination(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip_with_far_pickup,
        mock_osrm_client_for_proximity,
        mock_kafka_producer,
        proximity_settings,
    ):
        """Test that driver location updates toward destination during trip."""
        initial_location = driver_agent.location

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip_with_far_pickup,
            osrm_client=mock_osrm_client_for_proximity,
            kafka_producer=mock_kafka_producer,
            settings=proximity_settings,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Final location should be at dropoff
        final_location = driver_agent.location
        assert final_location != initial_location
        # Should be at or near dropoff location
        assert final_location == trip_with_far_pickup.dropoff_location


class TestSimulationSettingsValidation:
    """Tests for SimulationSettings validation."""

    def test_valid_proximity_threshold(self):
        """Test valid proximity threshold values."""
        settings = SimulationSettings(arrival_proximity_threshold_m=50.0)
        assert settings.arrival_proximity_threshold_m == 50.0

        settings = SimulationSettings(arrival_proximity_threshold_m=10.0)
        assert settings.arrival_proximity_threshold_m == 10.0

        settings = SimulationSettings(arrival_proximity_threshold_m=500.0)
        assert settings.arrival_proximity_threshold_m == 500.0

    def test_proximity_threshold_minimum(self):
        """Test that proximity threshold has a minimum value."""
        with pytest.raises(ValueError):
            SimulationSettings(arrival_proximity_threshold_m=5.0)  # Below 10m minimum

    def test_proximity_threshold_maximum(self):
        """Test that proximity threshold has a maximum value."""
        with pytest.raises(ValueError):
            SimulationSettings(
                arrival_proximity_threshold_m=600.0
            )  # Above 500m maximum

    def test_valid_timeout_multiplier(self):
        """Test valid timeout multiplier values."""
        settings = SimulationSettings(arrival_timeout_multiplier=1.5)
        assert settings.arrival_timeout_multiplier == 1.5

        settings = SimulationSettings(arrival_timeout_multiplier=2.0)
        assert settings.arrival_timeout_multiplier == 2.0

    def test_timeout_multiplier_minimum(self):
        """Test that timeout multiplier has a minimum value."""
        with pytest.raises(ValueError):
            SimulationSettings(arrival_timeout_multiplier=0.5)  # Below 1.0 minimum

    def test_timeout_multiplier_maximum(self):
        """Test that timeout multiplier has a maximum value."""
        with pytest.raises(ValueError):
            SimulationSettings(arrival_timeout_multiplier=6.0)  # Above 5.0 maximum
