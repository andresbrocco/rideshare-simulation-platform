"""Tests for TripExecutor error recovery and retry logic.

This module tests the error handling improvements for PATTERN-006:
- Retry logic for transient OSRM failures
- Cleanup handler for unrecoverable errors
- Agent state restoration after failures
"""

from unittest.mock import Mock, call

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.geo.osrm_client import (
    NoRouteFoundError,
    OSRMServiceError,
    OSRMTimeoutError,
    RouteResponse,
)
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
        driver_id="driver_recovery_001",
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
        rider_id="rider_recovery_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.54, -46.62)
    return agent


@pytest.fixture
def sample_trip():
    return Trip(
        trip_id="trip_recovery_001",
        rider_id="rider_recovery_001",
        driver_id="driver_recovery_001",
        state=TripState.MATCHED,
        pickup_location=(-23.54, -46.62),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone_1",
        dropoff_zone_id="zone_2",
        surge_multiplier=1.0,
        fare=25.50,
    )


@pytest.fixture
def mock_matching_server():
    server = Mock()
    server.complete_trip = Mock()
    return server


def create_successful_route(origin, destination):
    """Create a successful route response."""
    num_points = 11
    geometry = []
    for i in range(num_points):
        progress = i / (num_points - 1)
        lat = origin[0] + (destination[0] - origin[0]) * progress
        lon = origin[1] + (destination[1] - origin[1]) * progress
        geometry.append((lat, lon))
    return RouteResponse(
        distance_meters=2000.0,
        duration_seconds=10.0,  # Short for fast tests
        geometry=geometry,
        osrm_code="Ok",
    )


class TestRetrySettingsConfiguration:
    """Tests for OSRM retry configuration in settings."""

    def test_default_retry_settings(self):
        settings = SimulationSettings()
        assert settings.osrm_max_retries == 3
        assert settings.osrm_retry_base_delay == 0.5
        assert settings.osrm_retry_multiplier == 2.0

    def test_custom_retry_settings(self):
        settings = SimulationSettings(
            osrm_max_retries=5,
            osrm_retry_base_delay=1.0,
            osrm_retry_multiplier=3.0,
        )
        assert settings.osrm_max_retries == 5
        assert settings.osrm_retry_base_delay == 1.0
        assert settings.osrm_retry_multiplier == 3.0

    def test_retry_settings_validation(self):
        # Max retries must be >= 0
        with pytest.raises(ValueError):
            SimulationSettings(osrm_max_retries=-1)

        # Max retries must be <= 10
        with pytest.raises(ValueError):
            SimulationSettings(osrm_max_retries=11)


class TestOSRMRetryLogic:
    """Tests for exponential backoff retry on OSRM failures."""

    def test_successful_after_transient_failure(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Trip succeeds after retrying a transient OSRM failure."""
        call_count = 0

        def mock_route(origin, destination):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSRMTimeoutError("Timeout on first attempt")
            return create_successful_route(origin, destination)

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=mock_route)

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=3,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.COMPLETED
        assert call_count >= 2  # At least one retry

    def test_retries_osrm_service_error(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """OSRM service errors (5xx) trigger retries."""
        call_count = 0

        def mock_route(origin, destination):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OSRMServiceError("Server error 503")
            return create_successful_route(origin, destination)

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=mock_route)

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=3,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.COMPLETED
        # Failed twice on pickup route, succeeded on third, then destination route succeeds
        assert call_count >= 3

    def test_no_retry_for_no_route_found(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """NoRouteFoundError does not trigger retries (not transient)."""
        call_count = 0

        def mock_route(origin, destination):
            nonlocal call_count
            call_count += 1
            raise NoRouteFoundError("No route between coordinates")

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=mock_route)

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=3,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Trip should be cancelled after NoRouteFoundError
        assert sample_trip.state == TripState.CANCELLED
        assert call_count == 1  # No retries for NoRouteFoundError

    def test_retry_exhaustion_triggers_cleanup(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Trip is cancelled after exhausting all retries."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Persistent failure"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=2,  # 3 attempts total
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED
        # 3 attempts: initial + 2 retries
        assert osrm_client.get_route_sync.call_count == 3

    def test_exponential_backoff_timing(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Verify exponential backoff delays between retries on pickup route."""
        timestamps = []

        def mock_route(origin, destination):
            timestamps.append(simpy_env.now)
            # Fail first 3 calls to pickup route, succeed on 4th
            if len(timestamps) < 4:
                raise OSRMTimeoutError("Retry")
            return create_successful_route(origin, destination)

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=mock_route)

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=3,
                osrm_retry_base_delay=0.5,
                osrm_retry_multiplier=2.0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.COMPLETED
        # 3 failures + 1 success on pickup, plus 1 for destination route = 5
        assert len(timestamps) >= 4

        # Check delays between first 4 calls (pickup route retries): 0.5, 1.0, 2.0
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]
        delay3 = timestamps[3] - timestamps[2]

        assert abs(delay1 - 0.5) < 0.01  # First retry after 0.5s
        assert abs(delay2 - 1.0) < 0.01  # Second retry after 1.0s
        assert abs(delay3 - 2.0) < 0.01  # Third retry after 2.0s


class TestCleanupHandler:
    """Tests for trip cleanup on unrecoverable failures."""

    def test_cleanup_cancels_trip(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Failed trip transitions to CANCELLED state."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Failure"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,  # Fail immediately
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED
        assert sample_trip.cancelled_by == "system"

    def test_cleanup_releases_driver(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Driver returns to online status after failure."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=NoRouteFoundError("No route"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Driver should be back online and available
        assert driver_agent.status == "online"

    def test_cleanup_releases_rider(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Rider returns to offline status after failure."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=NoRouteFoundError("No route"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Rider should be back to offline (can request another ride)
        assert rider_agent.status == "offline"

    def test_cleanup_emits_cancellation_event(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Cancellation event is emitted to Kafka on failure."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMServiceError("503"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Check Kafka received a cancellation event
        trip_events = [
            c for c in mock_kafka_producer.produce.call_args_list if c[1].get("topic") == "trips"
        ]
        assert len(trip_events) > 0

        # Find the cancellation event
        cancellation_events = [
            c for c in trip_events if "cancelled" in str(c[1].get("value", "")).lower()
        ]
        assert len(cancellation_events) > 0

    def test_cleanup_removes_from_matching_server(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Trip is removed from matching server tracking on failure."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Timeout"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        mock_matching_server.complete_trip.assert_called_once_with(sample_trip.trip_id, sample_trip)

    def test_cleanup_records_statistics(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Failure statistics are recorded for driver and rider."""
        initial_driver_cancelled = driver_agent.statistics.trips_cancelled
        initial_rider_cancelled = rider_agent.statistics.trips_cancelled

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMServiceError("Error"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert driver_agent.statistics.trips_cancelled == initial_driver_cancelled + 1
        assert rider_agent.statistics.trips_cancelled == initial_rider_cancelled + 1


class TestCleanupFromDifferentStates:
    """Tests for cleanup at different trip lifecycle stages."""

    def test_cleanup_during_pickup_drive(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Cleanup works when failure occurs during drive to pickup."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Timeout"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED
        assert sample_trip.cancellation_stage == "pickup"

    def test_cleanup_during_destination_drive(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Cleanup works when failure occurs during drive to destination."""
        call_count = 0

        def mock_route(origin, destination):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (pickup route) succeeds
                return create_successful_route(origin, destination)
            # Second call (destination route) fails
            raise OSRMTimeoutError("Timeout during trip")

        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=mock_route)

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED
        assert sample_trip.cancellation_stage == "in_transit"


class TestCleanupIdempotency:
    """Tests for idempotent cleanup operations."""

    def test_cleanup_is_idempotent(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Calling cleanup multiple times does not cause errors."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Failure"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Trip already cancelled
        assert sample_trip.state == TripState.CANCELLED

        # Manually calling cleanup again should not raise
        executor._cleanup_failed_trip(
            reason="test_duplicate",
            stage="test",
            error=None,
        )

        # State should still be cancelled
        assert sample_trip.state == TripState.CANCELLED

    def test_cleanup_handles_already_offline_agents(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """Cleanup handles agents that are already offline gracefully."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Failure"))

        # Force driver offline before failure (rider starts offline by default)
        driver_agent.go_offline()

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        # Should not raise despite driver being offline
        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED


class TestZeroRetryConfiguration:
    """Tests for disabled retry configuration."""

    def test_zero_retries_fails_immediately(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_kafka_producer,
        mock_matching_server,
    ):
        """With max_retries=0, failure happens on first error."""
        osrm_client = Mock()
        osrm_client.get_route_sync = Mock(side_effect=OSRMTimeoutError("Timeout"))

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=osrm_client,
            kafka_producer=mock_kafka_producer,
            matching_server=mock_matching_server,
            settings=SimulationSettings(
                arrival_proximity_threshold_m=50.0,
                osrm_max_retries=0,
            ),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert sample_trip.state == TripState.CANCELLED
        assert osrm_client.get_route_sync.call_count == 1
