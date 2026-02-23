"""Tests for MatchingServer."""

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


@pytest.fixture
def sample_driver_dna():
    return DriverDNA(
        acceptance_rate=0.8,
        cancellation_tendency=0.1,
        service_quality=0.9,
        response_time=5.0,
        min_rider_rating=3.5,
        surge_acceptance_modifier=1.3,
        home_location=(-23.55, -46.63),
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="Carlos",
        last_name="Silva",
        email="carlos@test.com",
        phone="+5511999999999",
    )


def create_mock_driver(
    driver_id: str, dna: DriverDNA, rating: float = 4.5, acceptance_rate: float = 0.8
):
    driver = Mock()
    driver.driver_id = driver_id
    driver.dna = dna
    driver.current_rating = rating
    driver.location = (-23.55, -46.63)
    driver.status = "available"
    driver.active_trip = None  # No active trip by default
    driver.receive_offer = Mock(return_value=True)
    driver._is_puppet = False  # Ensure mock drivers are not treated as puppets
    return driver


@pytest.mark.unit
@pytest.mark.critical
class TestMatchingServerInit:
    def test_matching_server_init(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        assert server._env is env
        assert server._driver_index is mock_driver_index
        assert server._notification_dispatch is mock_notification_dispatch
        assert server._osrm_client is mock_osrm_client
        assert server._kafka_producer is mock_kafka_producer
        assert server._pending_offers == {}


@pytest.mark.unit
@pytest.mark.critical
class TestFindNearbyDrivers:
    @pytest.mark.asyncio
    async def test_find_nearby_drivers(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        driver1 = create_mock_driver("driver-1", sample_driver_dna)
        driver2 = create_mock_driver("driver-2", sample_driver_dna)

        mock_driver_index.find_nearest_drivers.return_value = [
            ("driver-1", 2.5),
            ("driver-2", 3.0),
        ]

        route_response = Mock()
        route_response.duration_seconds = 600
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {"driver-1": driver1, "driver-2": driver2}

        result = await server.find_nearby_drivers((-23.55, -46.63), max_eta_seconds=900)

        assert len(result) == 2
        assert result[0][0].driver_id == "driver-1"
        assert result[0][1] == 600

    @pytest.mark.asyncio
    async def test_find_nearby_drivers_filters_by_eta(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        driver1 = create_mock_driver("driver-1", sample_driver_dna)
        driver1.location = (-23.55, -46.63)
        driver2 = create_mock_driver("driver-2", sample_driver_dna)
        driver2.location = (-23.60, -46.70)

        mock_driver_index.find_nearest_drivers.return_value = [
            ("driver-1", 2.5),
            ("driver-2", 15.0),
        ]

        call_count = [0]

        async def get_route_side_effect(origin, dest):
            call_count[0] += 1
            # First call is driver1, second is driver2
            if call_count[0] == 1:
                response = Mock()
                response.duration_seconds = 600
                return response
            else:
                response = Mock()
                response.duration_seconds = 1200
                return response

        mock_osrm_client.get_route.side_effect = get_route_side_effect

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {"driver-1": driver1, "driver-2": driver2}

        result = await server.find_nearby_drivers((-23.55, -46.63), max_eta_seconds=900)

        assert len(result) == 1
        assert result[0][0].driver_id == "driver-1"


def create_dna_with_acceptance_rate(acceptance_rate: float) -> DriverDNA:
    """Create a DriverDNA instance with a specific acceptance rate."""
    return DriverDNA(
        acceptance_rate=acceptance_rate,
        cancellation_tendency=0.1,
        service_quality=0.9,
        response_time=5.0,
        min_rider_rating=3.5,
        surge_acceptance_modifier=1.3,
        home_location=(-23.55, -46.63),
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="Carlos",
        last_name="Silva",
        email="carlos@test.com",
        phone="+5511999999999",
    )


@pytest.mark.unit
@pytest.mark.critical
class TestRankDrivers:
    def test_rank_drivers_by_composite_score(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        dna1 = create_dna_with_acceptance_rate(0.7)
        dna2 = create_dna_with_acceptance_rate(0.9)

        driver1 = create_mock_driver("driver-1", dna1, rating=4.0)
        driver2 = create_mock_driver("driver-2", dna2, rating=4.8)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        driver_eta_list = [
            (driver1, 300),
            (driver2, 600),
        ]

        ranked = server.rank_drivers(driver_eta_list)

        assert len(ranked) == 2
        # driver1 has better ETA, driver2 has better rating/acceptance
        # scores depend on normalization

    def test_composite_score_calculation(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        score = server._calculate_composite_score(
            eta_seconds=300,
            rating=4.5,
            acceptance_rate=0.8,
            min_eta=300,
            max_eta=600,
            eta_weight=0.5,
            rating_weight=0.3,
            acceptance_weight=0.2,
        )

        # ETA normalized: (600-300)/(600-300) = 1.0, weight 0.5 -> 0.5
        # Rating normalized: (4.5-1.0)/(5.0-1.0) = 0.875, weight 0.3 -> 0.2625
        # Acceptance: 0.8, weight 0.2 -> 0.16
        # Total: 0.5 + 0.2625 + 0.16 = 0.9225
        assert 0.9 <= score <= 0.95


@pytest.mark.unit
@pytest.mark.critical
class TestSendOffer:
    def test_send_offer_queues_deferred_response(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify send_offer() transitions to OFFER_SENT and queues a deferred response."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        result = server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        # send_offer() always returns False for regular drivers (result is async)
        assert result is False
        assert trip.state == TripState.OFFER_SENT
        assert trip.offer_sequence == 1
        # Deferred response should be queued
        assert len(server._pending_deferred_offers) == 1


@pytest.mark.unit
@pytest.mark.critical
class TestHandleOfferResponses:
    def test_deferred_offer_accepted(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify deferred offer acceptance applies after response_time delay."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )
        server._active_trips[trip.trip_id] = trip

        # Force acceptance decision
        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        # Process the queued deferred offer and run SimPy
        server.start_pending_trip_executions()
        env.run()

        # After response_time delay, trip should be matched
        assert trip.state == TripState.DRIVER_ASSIGNED
        assert trip.driver_id == "driver-1"
        driver.accept_trip.assert_called_once_with("trip-123")

    def test_deferred_offer_rejected(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify deferred offer rejection releases driver after response_time delay."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )
        server._active_trips[trip.trip_id] = trip

        # Force rejection decision
        with patch.object(server, "_compute_offer_decision", return_value=False):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        # Process the queued deferred offer and run SimPy
        server.start_pending_trip_executions()
        env.run()

        # After response_time delay, driver should be released
        assert "driver-1" not in server._reserved_drivers
        driver.statistics.record_offer_rejected.assert_called_once()

    def test_deferred_response_respects_response_time(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify the SimPy delay matches the driver's response_time DNA."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )
        server._active_trips[trip.trip_id] = trip

        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        server.start_pending_trip_executions()
        start_time = env.now

        # Trip should NOT be matched yet (deferred)
        assert trip.state == TripState.OFFER_SENT

        env.run()
        elapsed = env.now - start_time

        # response_time=5.0 with variance [-2,+2] → delay in [3.0, 7.0]
        assert 3.0 <= elapsed <= 7.0
        assert trip.state == TripState.DRIVER_ASSIGNED


@pytest.mark.unit
@pytest.mark.critical
class TestOfferCycle:
    def test_handle_offer_rejected_cycles_to_next(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify rejection cycles through remaining candidates."""
        driver1 = create_mock_driver("driver-1", sample_driver_dna)
        driver2 = create_mock_driver("driver-2", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [
            (driver1, 300, 0.9),
            (driver2, 400, 0.85),
        ]

        # First driver rejects, second accepts
        decisions = iter([False, True])
        with patch.object(server, "_compute_offer_decision", side_effect=decisions):
            result = server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

        assert result is not None

        # Process first deferred offer (driver1 rejects → queues driver2)
        server.start_pending_trip_executions()
        env.run()

        # Process second deferred offer (driver2 accepts)
        server.start_pending_trip_executions()
        env.run()

        assert trip.driver_id == "driver-2"
        assert trip.state == TripState.DRIVER_ASSIGNED
        assert trip.offer_sequence == 2

    def test_max_offer_attempts(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify max_attempts limits how many drivers get offers."""
        drivers = [create_mock_driver(f"driver-{i}", sample_driver_dna) for i in range(5)]

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [(d, 300 + i * 60, 0.9 - i * 0.01) for i, d in enumerate(drivers)]

        # All drivers reject — patch must cover the entire cycle including env.run()
        # because continuations call _compute_offer_decision from inside SimPy processes
        with patch.object(server, "_compute_offer_decision", return_value=False):
            server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

            # Process all 5 offers through the deferred cycle
            for _ in range(5):
                server.start_pending_trip_executions()
                env.run()

        # Trip should have no driver but stays alive for retry
        assert trip.trip_id in server._active_trips
        assert trip.trip_id in server._retry_queue
        # Count offers sent: 1 initial + 4 continuations = 5
        assert server._offers_sent == 5


@pytest.mark.unit
@pytest.mark.critical
class TestNoDriversAvailable:
    @pytest.mark.asyncio
    async def test_no_drivers_in_range(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        mock_driver_index.find_nearest_drivers.return_value = []

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {}

        result = await server.find_nearby_drivers((-23.55, -46.63), max_eta_seconds=900)

        assert result == []


@pytest.mark.unit
@pytest.mark.critical
class TestMatchFlow:
    @pytest.mark.asyncio
    async def test_match_flow_happy_path(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        driver = create_mock_driver("driver-1", sample_driver_dna)

        mock_driver_index.find_nearest_drivers.return_value = [("driver-1", 2.5)]

        route_response = Mock()
        route_response.duration_seconds = 600
        route_response.geometry = [[-23.55, -46.63], [-23.56, -46.64]]
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {"driver-1": driver}

        # Force acceptance
        with patch.object(server, "_compute_offer_decision", return_value=True):
            result = await server.request_match(
                rider_id="rider-456",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )

        assert result is not None
        # Trip is pending (deferred), not yet matched
        assert result.state == TripState.OFFER_SENT

        # Process deferred offer and run SimPy
        server.start_pending_trip_executions()
        env.run()

        assert result.driver_id == "driver-1"
        assert result.state == TripState.DRIVER_ASSIGNED
        assert result.offer_sequence == 1

    @pytest.mark.asyncio
    async def test_match_flow_multiple_rejections(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        drivers = [create_mock_driver(f"driver-{i}", sample_driver_dna) for i in range(4)]

        mock_driver_index.find_nearest_drivers.return_value = [
            (f"driver-{i}", 2.0 + i * 0.5) for i in range(4)
        ]

        route_response = Mock()
        route_response.duration_seconds = 600
        route_response.geometry = [[-23.55, -46.63], [-23.56, -46.64]]
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {f"driver-{i}": d for i, d in enumerate(drivers)}

        # First 3 reject, last accepts — patch must cover the entire cycle
        decisions = iter([False, False, False, True])
        with patch.object(server, "_compute_offer_decision", side_effect=decisions):
            result = await server.request_match(
                rider_id="rider-456",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )

            assert result is not None

            # Process all deferred offers through the cycle
            for _ in range(4):
                server.start_pending_trip_executions()
                env.run()

        assert result.driver_id == "driver-3"
        assert result.state == TripState.DRIVER_ASSIGNED
        assert result.offer_sequence == 4

    @pytest.mark.asyncio
    async def test_match_flow_no_match(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        drivers = [create_mock_driver(f"driver-{i}", sample_driver_dna) for i in range(3)]

        mock_driver_index.find_nearest_drivers.return_value = [
            (f"driver-{i}", 2.0 + i * 0.5) for i in range(3)
        ]

        route_response = Mock()
        route_response.duration_seconds = 600
        route_response.geometry = [[-23.55, -46.63], [-23.56, -46.64]]
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {f"driver-{i}": d for i, d in enumerate(drivers)}

        # All drivers reject — patch must cover the entire cycle
        with patch.object(server, "_compute_offer_decision", return_value=False):
            result = await server.request_match(
                rider_id="rider-456",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )

            # Trip returned as pending, but will fail after all rejections
            assert result is not None

            # Process all deferred offers
            for _ in range(3):
                server.start_pending_trip_executions()
                env.run()

        # Trip stays alive for retry after all rejections
        assert result.trip_id in server._active_trips
        assert result.trip_id in server._retry_queue


@pytest.mark.unit
@pytest.mark.critical
class TestDeferredOfferCancellation:
    """Tests for rider cancellation during driver think time."""

    def test_rider_cancels_during_think_time(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify deferred response exits cleanly if trip cancelled during think time."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [(driver, 300, 0.9)]

        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.send_offer_cycle(trip, ranked_drivers)

        # Start the deferred offer
        server.start_pending_trip_executions()

        # Simulate rider patience timeout: cancel trip before driver responds
        server.cancel_trip("trip-123", cancelled_by="rider", reason="patience_timeout")

        # Run SimPy — deferred response fires but trip is gone
        env.run()

        # Driver should be released, trip should NOT be matched
        assert "driver-1" not in server._reserved_drivers
        assert trip.state != TripState.DRIVER_ASSIGNED


@pytest.mark.unit
@pytest.mark.critical
class TestPuppetReOfferFlow:
    """Tests for puppet driver rejection continuing to next candidate."""

    def test_puppet_reject_continues_to_next_driver(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify that puppet rejection triggers offer to next driver."""
        # Create a puppet driver (first) and a regular driver (second)
        puppet_driver = create_mock_driver("puppet-driver", sample_driver_dna)
        puppet_driver._is_puppet = True

        regular_driver = create_mock_driver("regular-driver", sample_driver_dna)
        regular_driver._is_puppet = False

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {
            "puppet-driver": puppet_driver,
            "regular-driver": regular_driver,
        }

        # Add statistics mock to drivers
        puppet_driver.statistics = Mock()
        regular_driver.statistics = Mock()

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [
            (puppet_driver, 300, 0.9),
            (regular_driver, 400, 0.85),
        ]

        # Start the offer cycle - will pause at puppet driver
        server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

        # Should have stored remaining candidates
        assert trip.trip_id in server._pending_offer_candidates
        assert len(server._pending_offer_candidates[trip.trip_id]["remaining_drivers"]) == 1

        # Puppet rejects - should queue next offer for regular driver
        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.process_puppet_reject("puppet-driver", "trip-123")

        # Process the deferred offer for regular driver
        server.start_pending_trip_executions()
        env.run()

        # Trip should now be matched with regular driver
        assert trip.driver_id == "regular-driver"
        assert trip.state == TripState.DRIVER_ASSIGNED

    def test_puppet_reject_chain(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Multiple puppet drivers reject in sequence."""
        # Create 3 puppet drivers
        puppets = []
        for i in range(3):
            p = create_mock_driver(f"puppet-{i}", sample_driver_dna)
            p._is_puppet = True
            p.statistics = Mock()
            puppets.append(p)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {p.driver_id: p for p in puppets}

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [(p, 300 + i * 60, 0.9 - i * 0.01) for i, p in enumerate(puppets)]

        # Start cycle - pauses at puppet-0
        server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)
        assert trip.trip_id in server._pending_offer_candidates
        assert len(server._pending_offer_candidates[trip.trip_id]["remaining_drivers"]) == 2

        # Reject puppet-0 - should pause at puppet-1
        server.process_puppet_reject("puppet-0", "trip-123")
        assert trip.trip_id in server._pending_offer_candidates
        assert len(server._pending_offer_candidates[trip.trip_id]["remaining_drivers"]) == 1

        # Reject puppet-1 - should pause at puppet-2
        server.process_puppet_reject("puppet-1", "trip-123")
        assert trip.trip_id in server._pending_offer_candidates
        assert len(server._pending_offer_candidates[trip.trip_id]["remaining_drivers"]) == 0

    def test_puppet_reject_exhausts_all_candidates(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """All candidates exhausted after puppet rejections emits no_drivers."""
        puppet = create_mock_driver("puppet-1", sample_driver_dna)
        puppet._is_puppet = True
        puppet.statistics = Mock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {"puppet-1": puppet}

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [(puppet, 300, 0.9)]

        # Start cycle - only one candidate
        server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)
        assert trip.trip_id in server._pending_offer_candidates
        assert len(server._pending_offer_candidates[trip.trip_id]["remaining_drivers"]) == 0

        # Track the trip as active
        assert trip.trip_id in server._active_trips

        # Reject - should emit no_drivers and add to retry queue
        server.process_puppet_reject("puppet-1", "trip-123")

        # Trip stays alive for retry
        assert trip.trip_id in server._active_trips
        assert trip.trip_id in server._retry_queue
        assert trip.trip_id not in server._pending_offer_candidates

    def test_puppet_timeout_continues_to_next_driver(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify that puppet timeout triggers offer to next driver."""
        puppet_driver = create_mock_driver("puppet-driver", sample_driver_dna)
        puppet_driver._is_puppet = True
        puppet_driver.statistics = Mock()

        regular_driver = create_mock_driver("regular-driver", sample_driver_dna)
        regular_driver._is_puppet = False
        regular_driver.statistics = Mock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {
            "puppet-driver": puppet_driver,
            "regular-driver": regular_driver,
        }

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [
            (puppet_driver, 300, 0.9),
            (regular_driver, 400, 0.85),
        ]

        # Start the offer cycle - will pause at puppet driver
        server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

        # Puppet times out - should queue next offer for regular driver
        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.process_puppet_timeout("puppet-driver", "trip-123")

        # Process the deferred offer for regular driver
        server.start_pending_trip_executions()
        env.run()

        # Trip should now be matched with regular driver
        assert trip.driver_id == "regular-driver"
        assert trip.state == TripState.DRIVER_ASSIGNED


@pytest.mark.unit
@pytest.mark.critical
class TestComputeOfferDecision:
    """Tests for the _compute_offer_decision pure function."""

    def test_base_acceptance_rate(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify base acceptance rate is used for non-surge trips."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        # With acceptance_rate=0.8, random < 0.8 → accept
        with patch("matching.matching_server.random.random", return_value=0.5):
            assert server._compute_offer_decision(driver, trip) is True

        # random >= 0.8 → reject
        with patch("matching.matching_server.random.random", return_value=0.9):
            assert server._compute_offer_decision(driver, trip) is False

    def test_surge_increases_acceptance(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify surge multiplier increases acceptance probability."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=2.0,  # 2x surge
            fare=50.00,
        )

        # acceptance_rate=0.8, surge_acceptance_modifier=1.3
        # adjusted = 0.8 * (1 + (2.0-1.0) * 1.3) = 0.8 * 2.3 = 1.84 → capped at 1.0
        with patch("matching.matching_server.random.random", return_value=0.95):
            assert server._compute_offer_decision(driver, trip) is True

    def test_low_rider_rating_reduces_acceptance(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Verify low rider rating reduces acceptance probability."""
        driver = create_mock_driver("driver-1", sample_driver_dna)

        mock_rider = Mock()
        mock_rider.current_rating = 2.5  # Below min_rider_rating=3.5
        mock_registry = Mock()
        mock_registry.get_rider.return_value = mock_rider

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            registry_manager=mock_registry,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        # acceptance_rate=0.8, rating penalty: 0.8 * (2.5/3.5) = 0.571
        with patch("matching.matching_server.random.random", return_value=0.7):
            assert server._compute_offer_decision(driver, trip) is False


@pytest.mark.unit
@pytest.mark.critical
class TestMatchingServerKafkaOnly:
    """Tests to verify MatchingServer emits trip state events to Kafka only, not Redis."""

    def test_matching_server_trip_state_emits_kafka_only(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        mock_redis_publisher = AsyncMock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,
        )

        trip = Trip(
            trip_id="trip-kafka-only-test",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        server._emit_trip_state_event(trip, "trip.driver_assigned")

        assert mock_kafka_producer.produce.called
        kafka_calls = mock_kafka_producer.produce.call_args_list
        trip_kafka_calls = [call for call in kafka_calls if call[1].get("topic") == "trips"]
        assert len(trip_kafka_calls) > 0

        redis_calls = mock_redis_publisher.publish.call_args_list
        assert len(redis_calls) == 0

    def test_matching_server_works_without_redis_publisher(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=None,
        )

        trip = Trip(
            trip_id="trip-no-redis-test",
            rider_id="rider-789",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        server._emit_trip_state_event(trip, "trip.completed")
        assert mock_kafka_producer.produce.called


@pytest.mark.unit
@pytest.mark.critical
class TestRouteClearOnCancellation:
    def test_cancelled_trip_emits_to_kafka(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        mock_redis_publisher = AsyncMock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )
        trip.route = [[-23.55, -46.63], [-23.56, -46.64]]
        trip.pickup_route = [[-23.54, -46.62], [-23.55, -46.63]]

        server._active_trips[trip.trip_id] = trip
        server._emit_trip_state_event(trip, "trip.cancelled")

        assert mock_kafka_producer.produce.called
        kafka_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        assert len(kafka_calls) > 0
        assert not mock_redis_publisher.publish.called

    def test_non_cancelled_trip_emits_to_kafka(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        mock_redis_publisher = AsyncMock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,
        )

        trip = Trip(
            trip_id="trip-123",
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )
        trip.route = [[-23.55, -46.63], [-23.56, -46.64]]
        trip.pickup_route = [[-23.54, -46.62], [-23.55, -46.63]]

        trip.transition_to(TripState.OFFER_SENT)
        trip.transition_to(TripState.DRIVER_ASSIGNED)

        server._emit_trip_state_event(trip, "trip.driver_assigned")

        assert mock_kafka_producer.produce.called
        kafka_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        assert len(kafka_calls) > 0
        assert not mock_redis_publisher.publish.called


@pytest.mark.unit
@pytest.mark.critical
class TestBoundedTripHistory:
    def test_completed_trips_bounded_by_max_trip_history(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        from settings import Settings

        settings = Settings()
        settings.matching.max_trip_history = 5

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            settings=settings,
        )

        for i in range(10):
            trip = Trip(
                trip_id=f"trip-{i}",
                rider_id=f"rider-{i}",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )
            trip.transition_to(TripState.OFFER_SENT)
            trip.transition_to(TripState.DRIVER_ASSIGNED)
            trip.transition_to(TripState.EN_ROUTE_PICKUP)
            trip.transition_to(TripState.AT_PICKUP)
            trip.transition_to(TripState.IN_TRANSIT)
            trip.transition_to(TripState.COMPLETED)

            server._active_trips[trip.trip_id] = trip
            server.complete_trip(trip.trip_id, trip)

        completed = server.get_completed_trips()
        assert len(completed) == 5

        trip_ids = [t.trip_id for t in completed]
        assert "trip-0" not in trip_ids
        assert "trip-4" not in trip_ids
        assert "trip-5" in trip_ids
        assert "trip-9" in trip_ids

    def test_cancelled_trips_bounded_by_max_trip_history(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        from settings import Settings

        settings = Settings()
        settings.matching.max_trip_history = 3

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            settings=settings,
        )

        for i in range(7):
            trip = Trip(
                trip_id=f"cancelled-trip-{i}",
                rider_id=f"rider-{i}",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )
            trip.cancel(by="rider", reason="test", stage="requested")

            server._active_trips[trip.trip_id] = trip
            server.complete_trip(trip.trip_id, trip)

        cancelled = server.get_cancelled_trips()
        assert len(cancelled) == 3

        trip_ids = [t.trip_id for t in cancelled]
        assert "cancelled-trip-0" not in trip_ids
        assert "cancelled-trip-3" not in trip_ids
        assert "cancelled-trip-4" in trip_ids
        assert "cancelled-trip-6" in trip_ids

    def test_clear_reinitializes_bounded_deques(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        from settings import Settings

        settings = Settings()
        settings.matching.max_trip_history = 5

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            settings=settings,
        )

        for i in range(3):
            trip = Trip(
                trip_id=f"trip-{i}",
                rider_id=f"rider-{i}",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )
            trip.transition_to(TripState.OFFER_SENT)
            trip.transition_to(TripState.DRIVER_ASSIGNED)
            trip.transition_to(TripState.EN_ROUTE_PICKUP)
            trip.transition_to(TripState.AT_PICKUP)
            trip.transition_to(TripState.IN_TRANSIT)
            trip.transition_to(TripState.COMPLETED)
            server._active_trips[trip.trip_id] = trip
            server.complete_trip(trip.trip_id, trip)

        assert len(server.get_completed_trips()) == 3

        server.clear()

        assert len(server.get_completed_trips()) == 0
        assert len(server.get_cancelled_trips()) == 0

        for i in range(10):
            trip = Trip(
                trip_id=f"post-clear-trip-{i}",
                rider_id=f"rider-{i}",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.50,
            )
            trip.transition_to(TripState.OFFER_SENT)
            trip.transition_to(TripState.DRIVER_ASSIGNED)
            trip.transition_to(TripState.EN_ROUTE_PICKUP)
            trip.transition_to(TripState.AT_PICKUP)
            trip.transition_to(TripState.IN_TRANSIT)
            trip.transition_to(TripState.COMPLETED)
            server._active_trips[trip.trip_id] = trip
            server.complete_trip(trip.trip_id, trip)

        assert len(server.get_completed_trips()) == 5


@pytest.mark.unit
@pytest.mark.critical
class TestOSRMCandidateLimit:
    @pytest.mark.asyncio
    async def test_osrm_calls_limited_to_candidate_limit(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        drivers = {}
        nearby_results = []
        for i in range(20):
            d = create_mock_driver(f"driver-{i}", sample_driver_dna)
            drivers[f"driver-{i}"] = d
            nearby_results.append((f"driver-{i}", 1.0 + i * 0.5))

        mock_driver_index.find_nearest_drivers.return_value = nearby_results

        route_response = Mock()
        route_response.duration_seconds = 300
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = drivers
        server._osrm_candidate_limit = 5

        result = await server.find_nearby_drivers((-23.55, -46.63))

        assert mock_osrm_client.get_route.call_count == 5
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_osrm_limit_with_fewer_drivers_than_limit(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        drivers = {}
        nearby_results = []
        for i in range(3):
            d = create_mock_driver(f"driver-{i}", sample_driver_dna)
            drivers[f"driver-{i}"] = d
            nearby_results.append((f"driver-{i}", 1.0 + i * 0.5))

        mock_driver_index.find_nearest_drivers.return_value = nearby_results

        route_response = Mock()
        route_response.duration_seconds = 300
        mock_osrm_client.get_route.return_value = route_response

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = drivers
        server._osrm_candidate_limit = 15

        result = await server.find_nearby_drivers((-23.55, -46.63))

        assert mock_osrm_client.get_route.call_count == 3
        assert len(result) == 3


@pytest.mark.unit
@pytest.mark.critical
class TestRunningAccumulators:
    def test_get_trip_stats_from_accumulators(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        from datetime import UTC, datetime, timedelta

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        for i in range(3):
            trip = Trip(
                trip_id=f"trip-{i}",
                rider_id=f"rider-{i}",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.64),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=10.0 * (i + 1),
            )
            trip.requested_at = base_time
            trip.matched_at = base_time + timedelta(minutes=1)
            trip.driver_arrived_at = base_time + timedelta(minutes=3)
            trip.completed_at = base_time + timedelta(minutes=10 + i * 5)

            trip.transition_to(TripState.OFFER_SENT)
            trip.transition_to(TripState.DRIVER_ASSIGNED)
            trip.transition_to(TripState.EN_ROUTE_PICKUP)
            trip.transition_to(TripState.AT_PICKUP)
            trip.transition_to(TripState.IN_TRANSIT)
            trip.transition_to(TripState.COMPLETED)

            server._active_trips[trip.trip_id] = trip
            server.complete_trip(trip.trip_id, trip)

        stats = server.get_trip_stats()

        assert stats["completed_count"] == 3
        assert stats["avg_fare"] == 20.0
        assert abs(stats["avg_duration_minutes"] - 14.0) < 0.01
        assert abs(stats["avg_match_seconds"] - 60.0) < 0.01
        assert abs(stats["avg_pickup_seconds"] - 120.0) < 0.01

    def test_accumulators_reset_on_clear(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        from datetime import UTC, datetime, timedelta

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        trip = Trip(
            trip_id="trip-0",
            rider_id="rider-0",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=50.0,
        )
        trip.requested_at = base_time
        trip.matched_at = base_time + timedelta(minutes=1)
        trip.driver_arrived_at = base_time + timedelta(minutes=3)
        trip.completed_at = base_time + timedelta(minutes=10)

        trip.transition_to(TripState.OFFER_SENT)
        trip.transition_to(TripState.DRIVER_ASSIGNED)
        trip.transition_to(TripState.EN_ROUTE_PICKUP)
        trip.transition_to(TripState.AT_PICKUP)
        trip.transition_to(TripState.IN_TRANSIT)
        trip.transition_to(TripState.COMPLETED)

        server._active_trips[trip.trip_id] = trip
        server.complete_trip(trip.trip_id, trip)

        assert server.get_trip_stats()["completed_count"] == 1

        server.clear()

        stats = server.get_trip_stats()
        assert stats["completed_count"] == 0
        assert stats["avg_fare"] == 0.0
        assert stats["avg_duration_minutes"] == 0.0

    def test_cancelled_trips_dont_accumulate_stats(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="cancelled-trip",
            rider_id="rider-0",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=100.0,
        )
        trip.cancel(by="rider", reason="test", stage="requested")

        server._active_trips[trip.trip_id] = trip
        server.complete_trip(trip.trip_id, trip)

        stats = server.get_trip_stats()
        assert stats["cancelled_count"] == 1
        assert stats["completed_count"] == 0
        assert stats["avg_fare"] == 0.0


@pytest.mark.unit
@pytest.mark.critical
class TestWeightParameterPassing:
    def test_score_identical_with_explicit_weights(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        eta_w = server._settings.matching.ranking_eta_weight
        rating_w = server._settings.matching.ranking_rating_weight
        acceptance_w = server._settings.matching.ranking_acceptance_weight

        score = server._calculate_composite_score(
            eta_seconds=400,
            rating=4.0,
            acceptance_rate=0.75,
            min_eta=200,
            max_eta=600,
            eta_weight=eta_w,
            rating_weight=rating_w,
            acceptance_weight=acceptance_w,
        )

        eta_norm = (600 - 400) / (600 - 200)
        rating_norm = (4.0 - 1.0) / 4.0
        acceptance_norm = 0.75
        expected = eta_norm * eta_w + rating_norm * rating_w + acceptance_norm * acceptance_w

        assert abs(score - expected) < 1e-10

    def test_rank_drivers_extracts_weights_from_settings(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        dna1 = create_dna_with_acceptance_rate(0.7)
        dna2 = create_dna_with_acceptance_rate(0.9)
        driver1 = create_mock_driver("driver-1", dna1, rating=4.0)
        driver2 = create_mock_driver("driver-2", dna2, rating=4.8)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        driver_eta_list = [(driver1, 300), (driver2, 600)]

        ranked = server.rank_drivers(driver_eta_list)

        assert len(ranked) == 2
        assert all(score > 0 for _, _, score in ranked)


@pytest.mark.unit
@pytest.mark.critical
class TestRetryQueue:
    """Tests for the matching retry queue."""

    @pytest.mark.asyncio
    async def test_no_drivers_queues_retry(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """No nearby drivers → trip stays active and enters retry queue."""
        mock_driver_index.find_nearest_drivers.return_value = []
        mock_osrm_client.get_route.return_value = Mock(geometry=[])

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        result = await server.request_match(
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        assert result is not None
        assert result.trip_id in server._active_trips
        assert result.trip_id in server._retry_queue

    @pytest.mark.asyncio
    async def test_retry_finds_driver(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Trip in retry queue gets matched when a driver becomes available."""
        mock_osrm_client.get_route.return_value = Mock(geometry=[], duration_seconds=300)
        # First call: no drivers. Subsequent calls: driver available.
        mock_driver_index.find_nearest_drivers.return_value = []

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        result = await server.request_match(
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        assert result is not None
        trip_id = result.trip_id
        assert trip_id in server._retry_queue

        # Advance past retry interval
        env.run(until=env.now + server._settings.matching.retry_interval_seconds)

        # Now a driver is available
        driver = create_mock_driver("driver-1", sample_driver_dna)
        server._drivers["driver-1"] = driver
        mock_driver_index.find_nearest_drivers.return_value = [("driver-1", 2.5)]

        with patch.object(server, "_compute_offer_decision", return_value=True):
            await server.retry_pending_matches()

        # Trip should be removed from retry queue
        assert trip_id not in server._retry_queue

        # Process deferred offer and run SimPy
        server.start_pending_trip_executions()
        env.run()

        assert result.state == TripState.DRIVER_ASSIGNED
        assert result.driver_id == "driver-1"

    @pytest.mark.asyncio
    async def test_retry_interval_respected(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Retry does not trigger before the interval elapses."""
        mock_osrm_client.get_route.return_value = Mock(geometry=[], duration_seconds=300)
        mock_driver_index.find_nearest_drivers.return_value = []

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        result = await server.request_match(
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        trip_id = result.trip_id
        initial_retry_time = server._retry_queue[trip_id]

        # Add a driver but don't advance time past the interval
        driver = create_mock_driver("driver-1", sample_driver_dna)
        server._drivers["driver-1"] = driver
        mock_driver_index.find_nearest_drivers.return_value = [("driver-1", 2.5)]

        # Call retry before interval — should not search
        await server.retry_pending_matches()

        # Trip should still be in retry queue (not enough sim-time elapsed)
        assert trip_id in server._retry_queue
        assert server._retry_queue[trip_id] == initial_retry_time

    @pytest.mark.asyncio
    async def test_rider_cancels_during_retry(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Rider cancellation removes trip from both active trips and retry queue."""
        mock_osrm_client.get_route.return_value = Mock(geometry=[])
        mock_driver_index.find_nearest_drivers.return_value = []

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        result = await server.request_match(
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        trip_id = result.trip_id
        assert trip_id in server._retry_queue
        assert trip_id in server._active_trips

        server.cancel_trip(trip_id, cancelled_by="rider", reason="patience_timeout")

        assert trip_id not in server._retry_queue
        assert trip_id not in server._active_trips

    @pytest.mark.asyncio
    async def test_multiple_retries_until_success(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """Trip retries multiple times before finally matching."""
        mock_osrm_client.get_route.return_value = Mock(geometry=[], duration_seconds=300)
        mock_driver_index.find_nearest_drivers.return_value = []

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        result = await server.request_match(
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        trip_id = result.trip_id
        interval = server._settings.matching.retry_interval_seconds

        # First retry — still no drivers
        env.run(until=env.now + interval)
        await server.retry_pending_matches()
        assert trip_id in server._retry_queue

        # Second retry — still no drivers
        env.run(until=env.now + interval)
        await server.retry_pending_matches()
        assert trip_id in server._retry_queue

        # Third retry — driver available
        env.run(until=env.now + interval)
        driver = create_mock_driver("driver-1", sample_driver_dna)
        server._drivers["driver-1"] = driver
        mock_driver_index.find_nearest_drivers.return_value = [("driver-1", 2.5)]

        with patch.object(server, "_compute_offer_decision", return_value=True):
            await server.retry_pending_matches()

        assert trip_id not in server._retry_queue

        server.start_pending_trip_executions()
        env.run()

        assert result.state == TripState.DRIVER_ASSIGNED
        assert result.driver_id == "driver-1"

    def test_all_candidates_reject_queues_retry(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        """All ranked drivers reject → trip enters retry queue."""
        driver1 = create_mock_driver("driver-1", sample_driver_dna)
        driver2 = create_mock_driver("driver-2", sample_driver_dna)

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip-retry",
            rider_id="rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        ranked_drivers = [
            (driver1, 300, 0.9),
            (driver2, 400, 0.85),
        ]

        with patch.object(server, "_compute_offer_decision", return_value=False):
            server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

            for _ in range(2):
                server.start_pending_trip_executions()
                env.run()

        # Trip should be in retry queue, not removed
        assert trip.trip_id in server._active_trips
        assert trip.trip_id in server._retry_queue

    def test_clear_resets_retry_queue(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """clear() empties the retry queue."""
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        server._retry_queue["trip-1"] = 100.0
        server._retry_queue["trip-2"] = 200.0

        server.clear()

        assert len(server._retry_queue) == 0

    def test_matching_stats_includes_retry_count(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """get_matching_stats() reports trips_awaiting_retry."""
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )

        server._retry_queue["trip-1"] = 100.0
        server._retry_queue["trip-2"] = 200.0

        stats = server.get_matching_stats()
        assert stats["trips_awaiting_retry"] == 2
