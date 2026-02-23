"""Tests for deferred driver offer response timing behavior.

The acceptance decision logic is tested in tests/matching/test_matching_server.py
(TestComputeOfferDecision). This module tests the SimPy timing behavior of
_deferred_offer_response() — that the avg_response_time DNA parameter produces
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
        "avg_response_time": 5.0,
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
    """Verify that deferred response delay reflects the driver's avg_response_time DNA."""

    def test_response_delay_matches_dna(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Delay should be max(3.0, gauss(avg_response_time, 3.0))."""
        dna = make_driver_dna(avg_response_time=5.0)
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

        # Fix gauss to return exactly avg_response_time so delay = 5.0
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=5.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()

            # Before the delay elapses — trip should still be pending
            env.run(until=4.9)
            assert trip.state == TripState.OFFER_SENT

            # After the delay — trip should be matched
            env.run(until=5.1)
            assert trip.state == TripState.DRIVER_ASSIGNED

    def test_response_delay_includes_variance(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Delay should include the Gaussian variance around avg_response_time."""
        dna = make_driver_dna(avg_response_time=6.0)
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

        # Fix gauss to return 7.5 → delay = max(3.0, 7.5) = 7.5
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=7.5),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()

            # Before the delay — still pending
            env.run(until=7.4)
            assert trip.state == TripState.OFFER_SENT

            # After the delay — matched
            env.run(until=7.6)
            assert trip.state == TripState.DRIVER_ASSIGNED

    def test_response_delay_variance_distribution(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Multiple runs should show response times >= 3.0 with variance around mean."""
        random.seed(42)
        delays: list[float] = []

        for i in range(20):
            local_env = simpy.Environment()
            dna = make_driver_dna(avg_response_time=8.0)
            driver = create_mock_driver(f"driver-{i}", dna)
            server = create_server(
                local_env,
                mock_driver_index,
                mock_notification_dispatch,
                mock_osrm_client,
                mock_kafka_producer,
            )
            # Disable timeout manager so we measure the pure response delay
            server._offer_timeout_manager = None
            trip = create_trip(trip_id=f"trip-{i}")
            server._active_trips[trip.trip_id] = trip

            with patch.object(server, "_compute_offer_decision", return_value=True):
                server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()
            local_env.run()
            delays.append(local_env.now)

        # All should be >= 3.0 (Gaussian with floor at 3.0)
        assert all(t >= 3.0 for t in delays)
        # With 20 samples, should see some variance (not all identical)
        assert max(delays) - min(delays) > 0.5


@pytest.mark.unit
class TestDeferredResponseTimeBounds:
    """Verify response delay is bounded with floor at 3.0."""

    def test_low_gauss_draw_bounded_at_3(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Gaussian draw below 3.0 is clamped to 3.0 floor."""
        dna = make_driver_dna(avg_response_time=3.0)
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

        # gauss returns 1.0 → max(3.0, 1.0) = 3.0
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=1.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()

            # Before the 3.0 floor — still pending
            env.run(until=2.9)
            assert trip.state == TripState.OFFER_SENT

            # After the 3.0 floor — matched
            env.run(until=3.1)
            assert trip.state == TripState.DRIVER_ASSIGNED

    def test_high_gauss_draw_no_ceiling(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Gaussian draw above mean is not capped — no upper ceiling.

        Disable the OfferTimeoutManager so the response delay (14s) can
        complete without the 10s timeout firing first.  This isolates the
        delay computation from the timeout race.
        """
        dna = make_driver_dna(avg_response_time=9.0)
        driver = create_mock_driver("driver-1", dna)
        server = create_server(
            env,
            mock_driver_index,
            mock_notification_dispatch,
            mock_osrm_client,
            mock_kafka_producer,
        )
        # Disable timeout manager so the 14s delay can complete
        server._offer_timeout_manager = None
        trip = create_trip()
        server._active_trips[trip.trip_id] = trip

        # gauss returns 14.0 → max(3.0, 14.0) = 14.0 (no ceiling)
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=14.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)
            server.start_pending_trip_executions()
            env.run()

        assert env.now == pytest.approx(14.0)
        assert trip.state == TripState.DRIVER_ASSIGNED

    def test_delay_always_at_least_3(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Even with extreme negative Gaussian draw, delay >= 3.0."""
        dna = make_driver_dna(avg_response_time=5.0)
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

        # gauss returns -5.0 → max(3.0, -5.0) = 3.0
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=-5.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()
            env.run(until=3.1)

        assert env.now >= 3.0


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
        dna = make_driver_dna(avg_response_time=3.0)
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
            patch("matching.matching_server.random.gauss", return_value=4.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()
            env.run(until=4.1)

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
        dna = make_driver_dna(avg_response_time=3.0)
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
            patch.object(server, "_compute_offer_decision", return_value=False),
            patch("matching.matching_server.random.gauss", return_value=4.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()
            env.run(until=4.1)

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
        """Trip should be OFFER_SENT (not MATCHED) before avg_response_time delay elapses."""
        dna = make_driver_dna(avg_response_time=9.0)
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

        # Use 9.0s delay (under the 10s timeout) so the response fires first
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=9.0),
        ):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

            server.start_pending_trip_executions()

            # Run only 5 seconds — before the 9s response delay
            env.run(until=5.0)
            assert trip.state == TripState.OFFER_SENT

            # Run past the response delay but before timeout event
            env.run(until=9.1)
            assert trip.state == TripState.DRIVER_ASSIGNED
