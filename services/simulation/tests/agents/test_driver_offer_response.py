"""Tests for deferred driver offer response timing behavior.

The acceptance decision logic is tested in tests/matching/test_matching_server.py
(TestComputeOfferDecision). This module tests the SimPy timing behavior of
_deferred_offer_response() — that the response_time DNA parameter produces
the correct delay before applying the decision.
"""

import random
from unittest.mock import AsyncMock, Mock, patch

import pytest
import simpy

from agents.dna import DriverDNA, ShiftPreference
from matching.driver_geospatial_index import DriverGeospatialIndex
from matching.matching_server import MatchingServer
from trip import Trip, TripState


@pytest.fixture
def env():
    return simpy.Environment()


@pytest.fixture
def mock_driver_index():
    index = Mock(spec=DriverGeospatialIndex)
    index.find_nearest_drivers.return_value = []
    index._driver_locations = {}
    return index


@pytest.fixture
def mock_osrm_client():
    client = Mock()
    client.get_route = AsyncMock()
    return client


@pytest.fixture
def mock_notification_dispatch():
    dispatch = Mock()
    dispatch.send_driver_offer = Mock(return_value=True)
    return dispatch


@pytest.fixture
def mock_kafka_producer():
    producer = Mock()
    producer.produce = Mock()
    return producer


def make_driver_dna(**overrides: float | str | tuple[float, float]) -> DriverDNA:
    defaults = {
        "acceptance_rate": 0.8,
        "cancellation_tendency": 0.1,
        "service_quality": 0.9,
        "response_time": 5.0,
        "min_rider_rating": 3.5,
        "surge_acceptance_modifier": 1.3,
        "home_location": (-23.55, -46.63),
        "shift_preference": ShiftPreference.MORNING,
        "avg_hours_per_day": 8,
        "avg_days_per_week": 5,
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
        "vehicle_year": 2020,
        "license_plate": "ABC-1234",
        "first_name": "Carlos",
        "last_name": "Silva",
        "email": "carlos@test.com",
        "phone": "+5511999999999",
    }
    defaults.update(overrides)
    return DriverDNA(**defaults)


def create_mock_driver(driver_id: str, dna: DriverDNA) -> Mock:
    driver = Mock()
    driver.driver_id = driver_id
    driver.dna = dna
    driver.current_rating = 4.5
    driver.status = "available"
    driver.active_trip = None
    driver._is_puppet = False
    driver.statistics = Mock()
    return driver


def create_trip(**overrides: str | float | tuple[float, float]) -> Trip:
    defaults = {
        "trip_id": "trip-001",
        "rider_id": "rider-001",
        "pickup_location": (-23.55, -46.63),
        "dropoff_location": (-23.56, -46.64),
        "pickup_zone_id": "centro",
        "dropoff_zone_id": "pinheiros",
        "surge_multiplier": 1.0,
        "fare": 25.50,
    }
    defaults.update(overrides)
    return Trip(**defaults)


def create_server(
    env: simpy.Environment,
    mock_driver_index: Mock,
    mock_notification_dispatch: Mock,
    mock_osrm_client: Mock,
    mock_kafka_producer: Mock,
) -> MatchingServer:
    return MatchingServer(
        env=env,
        driver_index=mock_driver_index,
        notification_dispatch=mock_notification_dispatch,
        osrm_client=mock_osrm_client,
        kafka_producer=mock_kafka_producer,
    )


@pytest.mark.unit
class TestDeferredResponseTiming:
    """Verify that deferred response delay reflects the driver's response_time DNA."""

    def test_response_delay_matches_dna(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Delay should be response_time ± 2s variance."""
        dna = make_driver_dna(response_time=5.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        # Fix variance to 0.0 so delay = exactly response_time
        # Patch must cover env.run() since _deferred_offer_response calls random.uniform
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=0.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()
            env.run()

        assert env.now == pytest.approx(5.0)
        assert trip.state == TripState.DRIVER_ASSIGNED

    def test_response_delay_includes_variance(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Delay should include the random variance [-2, +2]."""
        dna = make_driver_dna(response_time=6.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        # Fix variance to +1.5 → delay = 6.0 + 1.5 = 7.5
        # Patch must cover env.run() since _deferred_offer_response calls random.uniform
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=1.5),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()
            env.run()

        assert env.now == pytest.approx(7.5)

    def test_response_delay_variance_distribution(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Multiple runs should show response times in [response_time-2, response_time+2]."""
        random.seed(42)
        response_times: list[float] = []

        for i in range(20):
            local_env = simpy.Environment()
            dna = make_driver_dna(response_time=8.0)
            driver = create_mock_driver(f"driver-{i}", dna)
            server = create_server(
                local_env,
                mock_driver_index,
                mock_notification_dispatch,
                mock_osrm_client,
                mock_kafka_producer,
            )
            trip = create_trip(trip_id=f"trip-{i}")
            server._active_trips[trip.trip_id] = trip

            with patch.object(server, "_compute_offer_decision", return_value=True):
                server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()
            local_env.run()
            response_times.append(local_env.now)

        # All should be in [6.0, 10.0] (response_time=8.0 ± 2.0)
        assert all(6.0 <= t <= 10.0 for t in response_times)
        # With 20 samples, should see some variance (not all identical)
        assert max(response_times) - min(response_times) > 0.5


@pytest.mark.unit
class TestDeferredResponseTimeBounds:
    """Verify response delay is bounded within [0.0, 14.9]."""

    def test_low_response_time_bounded_at_zero(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """response_time=3.0 (min valid) with variance=-2.0 → delay=1.0 (not negative)."""
        dna = make_driver_dna(response_time=3.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=-2.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()
            env.run()

        # max(0.0, 3.0 + (-2.0)) = max(0.0, 1.0) = 1.0
        assert env.now == pytest.approx(1.0)
        assert trip.state == TripState.DRIVER_ASSIGNED

    def test_high_response_time_bounded_at_14_9(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """response_time=12.0 (max valid) with variance=+2.0 → clamped to 14.0."""
        dna = make_driver_dna(response_time=12.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=2.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()
            env.run()

        # min(14.9, 12.0 + 2.0) = min(14.9, 14.0) = 14.0
        assert env.now == pytest.approx(14.0)
        assert trip.state == TripState.DRIVER_ASSIGNED

    def test_response_time_always_under_15(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Even with max response_time=12.0 and max variance, delay < 15.0."""
        dna = make_driver_dna(response_time=12.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=2.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        server.start_pending_trip_executions()
        env.run()

        assert env.now < 15.0


@pytest.mark.unit
class TestDeferredResponseStateTransitions:
    """Verify state transitions for accepted and rejected deferred offers."""

    def test_accepted_offer_transitions_to_matched(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Accepted deferred offer transitions trip to MATCHED and calls accept_trip."""
        dna = make_driver_dna(response_time=3.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        server.start_pending_trip_executions()
        env.run()

        assert trip.state == TripState.DRIVER_ASSIGNED
        assert trip.driver_id == "driver-1"
        driver.accept_trip.assert_called_once_with("trip-001")
        driver.statistics.record_offer_accepted.assert_called_once()

    def test_rejected_offer_releases_driver(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Rejected deferred offer releases driver reservation and updates index."""
        dna = make_driver_dna(response_time=3.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with patch.object(server, "_compute_offer_decision", return_value=False):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        server.start_pending_trip_executions()
        env.run()

        assert "driver-1" not in server._reserved_drivers
        driver.statistics.record_offer_rejected.assert_called_once()
        mock_driver_index.update_driver_status.assert_called_with("driver-1", "available")

    def test_trip_not_matched_before_delay_elapses(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Trip should be OFFER_SENT (not MATCHED) before response_time delay elapses."""
        dna = make_driver_dna(response_time=10.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.uniform", return_value=0.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        server.start_pending_trip_executions()

        # Run only 5 seconds — before the 10s response_time
        env.run(until=5.0)
        assert trip.state == TripState.OFFER_SENT

        # Now run to completion — trip should be matched
        env.run()
        assert trip.state == TripState.DRIVER_ASSIGNED
