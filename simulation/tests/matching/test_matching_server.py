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
        preferred_zones=["centro", "pinheiros"],
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
    driver.status = "online"
    driver.active_trip = None  # No active trip by default
    driver.receive_offer = Mock(return_value=True)
    driver._is_puppet = False  # Ensure mock drivers are not treated as puppets
    return driver


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
        preferred_zones=["centro", "pinheiros"],
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
        )

        # ETA normalized: (600-300)/(600-300) = 1.0, weight 0.5 -> 0.5
        # Rating normalized: (4.5-1.0)/(5.0-1.0) = 0.875, weight 0.3 -> 0.2625
        # Acceptance: 0.8, weight 0.2 -> 0.16
        # Total: 0.5 + 0.2625 + 0.16 = 0.9225
        assert 0.9 <= score <= 0.95


class TestSendOffer:
    def test_send_offer_to_top_candidate(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
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

        server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        mock_notification_dispatch.send_driver_offer.assert_called_once()
        assert trip.state == TripState.OFFER_SENT
        assert trip.offer_sequence == 1


class TestHandleOfferResponses:
    def test_handle_offer_accepted(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        driver = create_mock_driver("driver-1", sample_driver_dna)
        mock_notification_dispatch.send_driver_offer.return_value = True

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

        accepted = server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        assert accepted is True

    def test_handle_offer_rejected(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
        sample_driver_dna,
    ):
        driver = create_mock_driver("driver-1", sample_driver_dna)
        mock_notification_dispatch.send_driver_offer.return_value = False

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

        accepted = server.send_offer(driver, trip, offer_sequence=1, eta_seconds=300)

        assert accepted is False


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
        driver1 = create_mock_driver("driver-1", sample_driver_dna)
        driver2 = create_mock_driver("driver-2", sample_driver_dna)

        mock_notification_dispatch.send_driver_offer.side_effect = [False, True]

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

        result = server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

        assert result is not None
        assert trip.driver_id == "driver-2"
        assert trip.state == TripState.MATCHED
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
        drivers = [create_mock_driver(f"driver-{i}", sample_driver_dna) for i in range(5)]

        mock_notification_dispatch.send_driver_offer.return_value = False

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

        result = server.send_offer_cycle(trip, ranked_drivers, max_attempts=5)

        assert result is None
        assert mock_notification_dispatch.send_driver_offer.call_count == 5


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
        mock_osrm_client.get_route.return_value = route_response

        mock_notification_dispatch.send_driver_offer.return_value = True

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {"driver-1": driver}

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
        assert result.driver_id == "driver-1"
        assert result.state == TripState.MATCHED
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
        mock_osrm_client.get_route.return_value = route_response

        mock_notification_dispatch.send_driver_offer.side_effect = [False, False, False, True]

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {f"driver-{i}": d for i, d in enumerate(drivers)}

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
        assert result.driver_id == "driver-3"
        assert result.state == TripState.MATCHED
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
        mock_osrm_client.get_route.return_value = route_response

        mock_notification_dispatch.send_driver_offer.return_value = False

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
        )
        server._drivers = {f"driver-{i}": d for i, d in enumerate(drivers)}

        result = await server.request_match(
            rider_id="rider-456",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.50,
        )

        assert result is None


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

        # Regular driver accepts offers
        mock_notification_dispatch.send_driver_offer.return_value = True

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

        # Puppet rejects - should continue to next driver
        server.process_puppet_reject("puppet-driver", "trip-123")

        # Trip should now be matched with regular driver
        assert trip.driver_id == "regular-driver"
        assert trip.state == TripState.MATCHED

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

        # Reject - should emit no_drivers and remove from active
        server.process_puppet_reject("puppet-1", "trip-123")

        # Trip should be removed from active trips
        assert trip.trip_id not in server._active_trips
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

        mock_notification_dispatch.send_driver_offer.return_value = True

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

        # Puppet times out - should continue to next driver
        server.process_puppet_timeout("puppet-driver", "trip-123")

        # Trip should now be matched with regular driver
        assert trip.driver_id == "regular-driver"
        assert trip.state == TripState.MATCHED


class TestMatchingServerKafkaOnly:
    """Tests to verify MatchingServer emits trip state events to Kafka only, not Redis.

    FINDING-002 states that 5 locations still publish directly to Redis,
    causing duplicate messages. MatchingServer._emit_trip_state_event is one of these.
    The fix is to have it emit to Kafka only.
    """

    def test_matching_server_trip_state_emits_kafka_only(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Verify _emit_trip_state_event uses Kafka only, not Redis.

        After the fix, MatchingServer should only emit trip state events
        to Kafka. The Redis publisher parameter should not be used for
        trip state events - the API layer handles Redis distribution.
        """
        mock_redis_publisher = AsyncMock()

        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,  # Should NOT be used for trip events
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

        # Emit a trip state event
        server._emit_trip_state_event(trip, "trip.matched")

        # Verify Kafka was called
        assert mock_kafka_producer.produce.called, "Trip state events should be sent to Kafka"

        kafka_calls = mock_kafka_producer.produce.call_args_list
        trip_kafka_calls = [call for call in kafka_calls if call[1].get("topic") == "trips"]
        assert len(trip_kafka_calls) > 0, "Trip state events should go to trips topic"

        # Verify Redis was NOT called for trip state events
        # After the fix, redis_publisher.publish should not be called
        redis_calls = mock_redis_publisher.publish.call_args_list

        assert len(redis_calls) == 0, (
            "Trip state events should NOT be published directly to Redis. "
            "They should flow through Kafka -> API layer -> Redis fanout."
        )

    def test_matching_server_works_without_redis_publisher(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Verify MatchingServer works correctly with redis_publisher=None.

        After the consolidation, redis_publisher should be optional and
        the server should work correctly without it for trip state events.
        """
        server = MatchingServer(
            env=env,
            driver_index=mock_driver_index,
            notification_dispatch=mock_notification_dispatch,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            redis_publisher=None,  # No Redis publisher
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

        # Should not raise any errors
        server._emit_trip_state_event(trip, "trip.completed")

        # Kafka should have received the event
        assert mock_kafka_producer.produce.called


class TestRouteClearOnCancellation:
    """Tests for route clearing when trips are cancelled.

    Note: After consolidation (FINDING-002 fix), trip state events are emitted
    to Kafka only - not directly to Redis. Route clearing logic now happens
    in the API layer's filtered fanout mechanism.
    """

    def test_cancelled_trip_emits_to_kafka(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Verify cancelled trips emit events to Kafka."""
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
        # Set routes on the trip
        trip.route = [[-23.55, -46.63], [-23.56, -46.64]]
        trip.pickup_route = [[-23.54, -46.62], [-23.55, -46.63]]

        # Track the trip
        server._active_trips[trip.trip_id] = trip

        # Emit a cancellation event
        server._emit_trip_state_event(trip, "trip.cancelled")

        # Verify Kafka was called
        assert mock_kafka_producer.produce.called
        kafka_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        assert len(kafka_calls) > 0

        # Verify Redis was NOT called (consolidation fix)
        assert not mock_redis_publisher.publish.called

    def test_non_cancelled_trip_emits_to_kafka(
        self,
        env,
        mock_driver_index,
        mock_notification_dispatch,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        """Verify non-cancelled events emit to Kafka."""
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
        # Set routes on the trip
        trip.route = [[-23.55, -46.63], [-23.56, -46.64]]
        trip.pickup_route = [[-23.54, -46.62], [-23.55, -46.63]]

        # Transition to matched state
        trip.transition_to(TripState.OFFER_SENT)
        trip.transition_to(TripState.MATCHED)

        # Emit a non-cancellation event
        server._emit_trip_state_event(trip, "trip.matched")

        # Verify Kafka was called
        assert mock_kafka_producer.produce.called
        kafka_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        assert len(kafka_calls) > 0

        # Verify Redis was NOT called (consolidation fix)
        assert not mock_redis_publisher.publish.called
