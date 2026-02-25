"""Diagnostic tests for puppet rider ↔ autonomous driver cross-matching.

These tests reproduce the scenario where a puppet rider requests a trip
while autonomous drivers are nearby and available. Each test isolates
a different layer of the matching pipeline to identify where the
cross-matching breaks down.
"""

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
def sample_driver_dna():
    return DriverDNA(
        acceptance_rate=0.8,
        cancellation_tendency=0.1,
        service_quality=0.9,
        avg_response_time=5.0,
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
    driver_id: str, dna: DriverDNA, location: tuple[float, float] = (-23.55, -46.63)
) -> Mock:
    driver = Mock()
    driver.driver_id = driver_id
    driver.dna = dna
    driver.current_rating = 4.5
    driver.location = location
    driver.status = "available"
    driver.active_trip = None
    driver._is_puppet = False
    driver.statistics = Mock()
    return driver


def create_mock_puppet_rider(rider_id: str) -> Mock:
    rider = Mock()
    rider.rider_id = rider_id
    rider._is_puppet = True
    rider.current_rating = 4.8
    rider.location = (-23.5505, -46.6305)
    rider.status = "idle"
    return rider


def create_mock_autonomous_rider(rider_id: str) -> Mock:
    rider = Mock()
    rider.rider_id = rider_id
    rider._is_puppet = False
    rider.current_rating = 4.5
    rider.location = (-23.5505, -46.6305)
    rider.status = "requesting"
    return rider


def make_server(env, driver_index=None, kafka_producer=None, osrm_client=None):
    if driver_index is None:
        driver_index = Mock(spec=DriverGeospatialIndex)
        driver_index.find_nearest_drivers.return_value = []
        driver_index._driver_locations = {}
    if osrm_client is None:
        osrm_client = Mock()
        osrm_client.get_route = AsyncMock()
    if kafka_producer is None:
        kafka_producer = Mock()
        kafka_producer.produce = Mock()

    return MatchingServer(
        env=env,
        driver_index=driver_index,
        notification_dispatch=Mock(),
        osrm_client=osrm_client,
        kafka_producer=kafka_producer,
    )


# ---------------------------------------------------------------------------
# Layer 1: Spatial index — do autonomous drivers show up in find_nearby?
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestLayer1SpatialDiscovery:
    """Verify that find_nearby_drivers returns autonomous drivers."""

    @pytest.mark.asyncio
    async def test_spatial_index_returns_autonomous_drivers(self, env, sample_driver_dna):
        """Use a REAL DriverGeospatialIndex (not a mock) to verify autonomous
        drivers placed near the puppet rider are actually discovered."""
        index = DriverGeospatialIndex(h3_resolution=9)

        # Place 3 autonomous drivers within 2km of the rider
        driver_locations = {
            "auto-driver-1": (-23.551, -46.631),  # ~150m away
            "auto-driver-2": (-23.553, -46.633),  # ~400m away
            "auto-driver-3": (-23.558, -46.638),  # ~1.1km away
        }
        for did, loc in driver_locations.items():
            index.add_driver(did, loc[0], loc[1], "available")

        rider_location = (-23.5505, -46.6305)
        results = index.find_nearest_drivers(
            rider_location[0],
            rider_location[1],
            radius_km=10.0,
            status_filter={"available", "driving_closer_to_home"},
        )

        found_ids = {r[0] for r in results}
        print(f"\n[Layer 1] Spatial index returned {len(results)} drivers: {found_ids}")
        for did, dist in results:
            print(f"  {did}: {dist:.3f} km")

        assert len(results) == 3, f"Expected 3 drivers, got {len(results)}: {found_ids}"

    @pytest.mark.asyncio
    async def test_find_nearby_drivers_with_autonomous_and_puppet_mix(self, env, sample_driver_dna):
        """find_nearby_drivers should return both puppet and autonomous drivers."""
        auto_driver = create_mock_driver("auto-driver", sample_driver_dna)
        puppet_driver = create_mock_driver("puppet-driver", sample_driver_dna)
        puppet_driver._is_puppet = True

        mock_index = Mock(spec=DriverGeospatialIndex)
        mock_index.find_nearest_drivers.return_value = [
            ("auto-driver", 1.0),
            ("puppet-driver", 1.5),
        ]
        mock_index._driver_locations = {}

        route_response = Mock()
        route_response.duration_seconds = 300
        osrm = Mock()
        osrm.get_route = AsyncMock(return_value=route_response)

        server = make_server(env, driver_index=mock_index, osrm_client=osrm)
        server._drivers = {
            "auto-driver": auto_driver,
            "puppet-driver": puppet_driver,
        }

        results = await server.find_nearby_drivers((-23.55, -46.63))
        found_ids = [r[0].driver_id for r in results]
        print(f"\n[Layer 1b] find_nearby_drivers returned: {found_ids}")
        for driver, eta in results:
            print(f"  {driver.driver_id}: ETA={eta}s, puppet={driver._is_puppet}")

        assert "auto-driver" in found_ids, "Autonomous driver not found"
        assert "puppet-driver" in found_ids, "Puppet driver not found"


# ---------------------------------------------------------------------------
# Layer 2: Offer cycle — does send_offer get called for autonomous drivers?
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestLayer2OfferSending:
    """Verify that the offer cycle sends offers to autonomous drivers
    when the trip was requested by a puppet rider."""

    def test_send_offer_cycle_sends_to_autonomous_driver(self, env, sample_driver_dna):
        """send_offer_cycle should call send_offer on autonomous drivers."""
        auto_driver = create_mock_driver("auto-driver", sample_driver_dna)

        server = make_server(env)
        server._drivers = {"auto-driver": auto_driver}

        trip = Trip(
            trip_id="trip-puppet-auto",
            rider_id="puppet-rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.0,
        )

        ranked = [(auto_driver, 300, 0.9)]

        with patch.object(server, "_compute_offer_decision", return_value=True) as mock_decide:
            server.send_offer_cycle(trip, ranked)

            print(f"\n[Layer 2] Trip state after send_offer_cycle: {trip.state}")
            print(f"  _compute_offer_decision called: {mock_decide.called}")
            print(f"  Pending deferred offers: {len(server._pending_deferred_offers)}")
            print(f"  Pending puppet offers: {server._pending_offers}")
            print(f"  Trip offer_sequence: {trip.offer_sequence}")

            # The offer should have been sent (not skipped)
            assert trip.state == TripState.OFFER_SENT
            assert mock_decide.called, "_compute_offer_decision was never called"

    def test_send_offer_updates_rider_trip_state_to_offer_sent(self, env, sample_driver_dna):
        """send_offer should set rider.update_trip_state('offer_sent')."""
        auto_driver = create_mock_driver("auto-driver", sample_driver_dna)
        mock_rider = create_mock_puppet_rider("puppet-rider-1")

        server = make_server(env)
        server._drivers = {"auto-driver": auto_driver}

        mock_registry = Mock()
        mock_registry.get_rider.return_value = mock_rider
        server._registry_manager = mock_registry

        trip = Trip(
            trip_id="trip-offer-state",
            rider_id="puppet-rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.0,
        )

        ranked = [(auto_driver, 300, 0.9)]

        with patch.object(server, "_compute_offer_decision", return_value=True):
            server.send_offer_cycle(trip, ranked)

        mock_registry.get_rider.assert_called_with("puppet-rider-1")
        mock_rider.update_trip_state.assert_called_with("offer_sent")

    def test_send_offer_to_puppet_driver_stores_pending(self, env, sample_driver_dna):
        """For comparison: puppet driver offer goes to _pending_offers."""
        puppet_driver = create_mock_driver("puppet-driver", sample_driver_dna)
        puppet_driver._is_puppet = True

        server = make_server(env)
        server._drivers = {"puppet-driver": puppet_driver}

        trip = Trip(
            trip_id="trip-auto-puppet",
            rider_id="auto-rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.0,
        )

        ranked = [(puppet_driver, 300, 0.9)]
        server.send_offer_cycle(trip, ranked)

        print(f"\n[Layer 2b] Trip state: {trip.state}")
        print(f"  Pending puppet offers: {server._pending_offers}")
        print(f"  Pending deferred offers: {len(server._pending_deferred_offers)}")

        assert "puppet-driver" in server._pending_offers
        assert trip.state == TripState.OFFER_SENT


# ---------------------------------------------------------------------------
# Layer 3: Deferred response — does it actually resolve?
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestLayer3DeferredResolution:
    """Verify the deferred offer response fires and resolves the trip."""

    def test_deferred_offer_resolves_after_step(self, env, sample_driver_dna):
        """After sending a deferred offer, stepping SimPy should resolve it."""
        auto_driver = create_mock_driver("auto-driver", sample_driver_dna)

        server = make_server(env)
        server._drivers = {"auto-driver": auto_driver}

        trip = Trip(
            trip_id="trip-deferred",
            rider_id="puppet-rider-1",
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="centro",
            dropoff_zone_id="pinheiros",
            surge_multiplier=1.0,
            fare=25.0,
        )

        ranked = [(auto_driver, 300, 0.9)]

        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=4.0),
        ):
            server.send_offer_cycle(trip, ranked)

            print("\n[Layer 3] Before step:")
            print(f"  Trip state: {trip.state}")
            print(f"  Pending deferred: {len(server._pending_deferred_offers)}")
            print(f"  Trip driver_id: {trip.driver_id}")

            # Simulate what step() does
            server.start_pending_trip_executions()
            print("  After start_pending_trip_executions:")
            print(f"    Pending deferred: {len(server._pending_deferred_offers)}")

            env.run(until=5)

            print("  After env.run(until=5):")
            print(f"    Trip state: {trip.state}")
            print(f"    Trip driver_id: {trip.driver_id}")

        assert (
            trip.state == TripState.DRIVER_ASSIGNED
        ), f"Expected DRIVER_ASSIGNED, got {trip.state}"
        assert trip.driver_id == "auto-driver"


# ---------------------------------------------------------------------------
# Layer 4: Full async flow — request_match with puppet rider + auto drivers
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestLayer4FullRequestMatch:
    """End-to-end: puppet rider calls request_match and autonomous drivers
    are discovered, offered, and the deferred response resolves."""

    @pytest.mark.asyncio
    async def test_puppet_rider_matches_with_autonomous_driver(self, env, sample_driver_dna):
        """The full flow: puppet rider → request_match → autonomous driver found
        → deferred offer → step → matched."""
        auto_driver = create_mock_driver("auto-driver", sample_driver_dna)
        puppet_rider = create_mock_puppet_rider("puppet-rider-1")

        mock_index = Mock(spec=DriverGeospatialIndex)
        mock_index.find_nearest_drivers.return_value = [("auto-driver", 1.0)]
        mock_index._driver_locations = {}

        route_response = Mock()
        route_response.duration_seconds = 300
        route_response.distance_meters = 2500
        route_response.geometry = [(-23.55, -46.63), (-23.56, -46.64)]
        osrm = Mock()
        osrm.get_route = AsyncMock(return_value=route_response)

        server = make_server(env, driver_index=mock_index, osrm_client=osrm)
        server._drivers = {"auto-driver": auto_driver}

        # Wire up registry manager so request_match can look up rider
        mock_registry = Mock()
        mock_registry.get_rider.return_value = puppet_rider
        server._registry_manager = mock_registry

        # Prevent TripExecutor from running (it needs richer mocks);
        # we only care about the matching/offer resolution here.
        with (
            patch.object(server, "_compute_offer_decision", return_value=True),
            patch("matching.matching_server.random.gauss", return_value=4.0),
            patch.object(server, "_start_trip_execution_internal"),
        ):
            trip = await server.request_match(
                rider_id="puppet-rider-1",
                pickup_location=(-23.5505, -46.6305),
                dropoff_location=(-23.57, -46.65),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.0,
            )

            print("\n[Layer 4] After request_match:")
            print(f"  Trip state: {trip.state}")
            print(f"  Trip driver_id: {trip.driver_id}")
            print(f"  Pending deferred: {len(server._pending_deferred_offers)}")
            print(f"  Pending puppet offers: {server._pending_offers}")
            print(f"  spatial index called: {mock_index.find_nearest_drivers.called}")

            # At this point the trip should be OFFER_SENT (waiting for SimPy)
            assert trip.state == TripState.OFFER_SENT
            assert len(server._pending_deferred_offers) == 1

            # Now simulate step() — this is what the simulation loop does
            server.start_pending_trip_executions()
            env.run(until=5)

            print("  After step simulation:")
            print(f"    Trip state: {trip.state}")
            print(f"    Trip driver_id: {trip.driver_id}")

        assert trip.state == TripState.DRIVER_ASSIGNED
        assert trip.driver_id == "auto-driver"

    @pytest.mark.asyncio
    async def test_puppet_rider_all_autonomous_reject_then_puppet_accepts(
        self, env, sample_driver_dna
    ):
        """Puppet rider: all autonomous drivers reject, then a puppet driver
        gets the offer and accepts via API."""
        auto1 = create_mock_driver("auto-1", sample_driver_dna)
        auto2 = create_mock_driver("auto-2", sample_driver_dna)
        puppet_driver = create_mock_driver("puppet-driver", sample_driver_dna)
        puppet_driver._is_puppet = True

        puppet_rider = create_mock_puppet_rider("puppet-rider-1")

        mock_index = Mock(spec=DriverGeospatialIndex)
        mock_index.find_nearest_drivers.return_value = [
            ("auto-1", 0.5),
            ("auto-2", 1.0),
            ("puppet-driver", 1.5),
        ]
        mock_index._driver_locations = {}

        route_response = Mock()
        route_response.duration_seconds = 300
        route_response.geometry = [[-23.55, -46.63], [-23.56, -46.64]]
        osrm = Mock()
        osrm.get_route = AsyncMock(return_value=route_response)

        server = make_server(env, driver_index=mock_index, osrm_client=osrm)
        server._drivers = {
            "auto-1": auto1,
            "auto-2": auto2,
            "puppet-driver": puppet_driver,
        }

        mock_registry = Mock()
        mock_registry.get_rider.return_value = puppet_rider
        server._registry_manager = mock_registry

        # Both autonomous drivers reject
        decisions = iter([False, False])
        with (
            patch.object(server, "_compute_offer_decision", side_effect=decisions),
            patch("matching.matching_server.random.gauss", return_value=4.0),
        ):
            trip = await server.request_match(
                rider_id="puppet-rider-1",
                pickup_location=(-23.5505, -46.6305),
                dropoff_location=(-23.57, -46.65),
                pickup_zone_id="centro",
                dropoff_zone_id="pinheiros",
                surge_multiplier=1.0,
                fare=25.0,
            )

            print("\n[Layer 4b] After request_match:")
            print(f"  Trip state: {trip.state}")
            print(f"  Pending deferred: {len(server._pending_deferred_offers)}")
            print(f"  Pending puppet offers: {server._pending_offers}")

            # Process deferred offers: auto-1 rejects → auto-2 rejects → puppet-driver
            for i in range(3):
                server.start_pending_trip_executions()
                env.run(until=(i + 1) * 5)
                print(
                    f"  After step {i+1}: state={trip.state}, "
                    f"deferred={len(server._pending_deferred_offers)}, "
                    f"puppet_offers={list(server._pending_offers.keys())}"
                )

        # Puppet driver should have received the offer
        print(f"  Final puppet_offers: {server._pending_offers}")
        assert "puppet-driver" in server._pending_offers, (
            f"Puppet driver never received offer. "
            f"Trip state={trip.state}, offers sent={trip.offer_sequence}"
        )

        # Accept the puppet offer
        server.process_puppet_accept("puppet-driver", trip.trip_id)
        assert trip.state == TripState.EN_ROUTE_PICKUP
        assert trip.driver_id == "puppet-driver"
