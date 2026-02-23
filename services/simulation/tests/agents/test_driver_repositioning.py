"""Tests for driver home repositioning behavior."""

from unittest.mock import Mock, patch

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from src.geo.osrm_client import RouteResponse
from tests.factories import DNAFactory


@pytest.fixture
def dna_factory():
    return DNAFactory(seed=42)


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


@pytest.fixture
def mock_osrm_client():
    client = Mock()
    # Default route response for repositioning
    client.get_route_sync.return_value = RouteResponse(
        distance_meters=15000,
        duration_seconds=600,
        geometry=[
            (-23.40, -46.50),
            (-23.42, -46.52),
            (-23.44, -46.54),
            (-23.46, -46.56),
            (-23.48, -46.58),
            (-23.50, -46.60),
        ],
        osrm_code="Ok",
    )
    return client


def _make_driver(
    simpy_env: simpy.Environment,
    dna_factory: DNAFactory,
    mock_kafka_producer: Mock,
    osrm_client: Mock | None = None,
    home_location: tuple[float, float] = (-23.56, -46.65),
) -> DriverAgent:
    dna = dna_factory.driver_dna(home_location=home_location)
    agent = DriverAgent(
        driver_id="driver_repo_001",
        dna=dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
        osrm_client=osrm_client,
    )
    return agent


@pytest.mark.unit
class TestCalculateRepositionTarget:
    def test_target_is_10km_from_home(self):
        """Target should be at (distance - 10km)/distance ratio along the line."""
        current = (-23.30, -46.40)
        home = (-23.56, -46.65)
        distance_km = 40.0

        target = DriverAgent._calculate_reposition_target(current, home, distance_km)

        # ratio = (40 - 10) / 40 = 0.75
        expected_lat = current[0] + 0.75 * (home[0] - current[0])
        expected_lon = current[1] + 0.75 * (home[1] - current[1])
        assert target[0] == pytest.approx(expected_lat)
        assert target[1] == pytest.approx(expected_lon)

    def test_target_with_60km_distance(self):
        """At 60 km, ratio = (60-10)/60 = 5/6, target is 5/6 along the way."""
        current = (0.0, 0.0)
        home = (0.6, 0.6)
        distance_km = 60.0

        target = DriverAgent._calculate_reposition_target(current, home, distance_km)

        expected_lat = 0.0 + (5 / 6) * 0.6
        expected_lon = 0.0 + (5 / 6) * 0.6
        assert target[0] == pytest.approx(expected_lat)
        assert target[1] == pytest.approx(expected_lon)

    def test_target_barely_over_threshold(self):
        """At 11 km, ratio = 1/11, target is very close to current."""
        current = (0.0, 0.0)
        home = (1.0, 1.0)
        distance_km = 11.0

        target = DriverAgent._calculate_reposition_target(current, home, distance_km)

        ratio = 1.0 / 11.0
        assert target[0] == pytest.approx(ratio * 1.0)
        assert target[1] == pytest.approx(ratio * 1.0)


@pytest.mark.unit
class TestDriveTowardHome:
    def test_repositioning_spawned_when_far_from_home(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Repositioning should be spawned when driver is >10 km from home."""
        # Home is at (-23.56, -46.65). Place driver far away (~35 km)
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)  # ~35 km from home

        trip = Mock()
        agent.on_trip_completed(trip)

        assert agent._reposition_process is not None
        assert agent._reposition_process.is_alive

    def test_no_repositioning_when_close_to_home(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """No repositioning should start when driver is <= 10 km from home."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        # Home is (-23.56, -46.65), stay close (~1 km away)
        agent.update_location(-23.555, -46.645)

        trip = Mock()
        agent.on_trip_completed(trip)

        # Process is spawned but should complete immediately (distance <= 10km)
        assert agent._reposition_process is not None
        # Run the env to let the generator return immediately
        simpy_env.run(until=simpy_env.now + 1)
        assert not agent._reposition_process.is_alive
        # OSRM should never have been called
        mock_osrm_client.get_route_sync.assert_not_called()

    def test_no_repositioning_without_osrm_client(
        self, simpy_env, dna_factory, mock_kafka_producer
    ):
        """No repositioning if no OSRM client is available."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, osrm_client=None)
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)

        assert agent._reposition_process is None

    def test_repositioning_updates_driver_location(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """During repositioning, driver location should be updated along route."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        initial_location = (-23.30, -46.40)
        agent.update_location(*initial_location)

        trip = Mock()
        agent.on_trip_completed(trip)

        # Run simulation for part of the drive
        simpy_env.run(until=simpy_env.now + 100)

        # Driver should have moved from initial location
        assert agent.location != initial_location

    def test_repositioning_sets_driving_closer_to_home_status(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Driver should transition to driving_closer_to_home during repositioning."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)  # ~35 km from home

        trip = Mock()
        agent.on_trip_completed(trip)

        # Let repositioning start (OSRM call + first yield in drive)
        simpy_env.run(until=simpy_env.now + 10)

        assert agent.status == "driving_closer_to_home"

    def test_repositioning_failure_returns_to_available(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Failed repositioning should set status back to available."""
        mock_osrm_client.get_route_sync.side_effect = Exception("OSRM unavailable")

        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)

        # Let the process run — should catch exception and fall back to available
        simpy_env.run(until=simpy_env.now + 10)
        assert agent.status == "available"

    def test_repositioning_handles_osrm_failure_gracefully(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """OSRM failure during repositioning should be caught without crashing."""
        mock_osrm_client.get_route_sync.side_effect = Exception("OSRM unavailable")

        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)

        # Let the process run — should catch exception and exit cleanly
        simpy_env.run(until=simpy_env.now + 10)
        assert agent.status == "available"


@pytest.mark.unit
class TestRepositioningInterrupt:
    def test_receive_offer_interrupts_repositioning(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Accepting a trip offer should interrupt active repositioning."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)

        # Let repositioning start
        simpy_env.run(until=simpy_env.now + 10)
        assert agent._reposition_process is not None
        assert agent._reposition_process.is_alive

        # Force acceptance (set acceptance_rate to 1.0 in DNA)
        with patch.object(agent, "_dna") as mock_dna:
            mock_dna.acceptance_rate = 1.0
            mock_dna.surge_acceptance_modifier = 1.0
            mock_dna.min_rider_rating = 1.0
            accepted = agent.receive_offer({"trip_id": "trip_123", "surge_multiplier": 1.0})

        assert accepted
        assert agent._reposition_process is None
        assert agent.status == "en_route_pickup"

    def test_reject_offer_does_not_interrupt_repositioning(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Rejecting a trip offer should leave repositioning running."""
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client)
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)
        simpy_env.run(until=simpy_env.now + 10)

        reposition_process = agent._reposition_process
        assert reposition_process is not None
        assert reposition_process.is_alive

        # Force rejection (set acceptance_rate to 0.0)
        with patch.object(agent, "_dna") as mock_dna:
            mock_dna.acceptance_rate = 0.0
            mock_dna.surge_acceptance_modifier = 0.0
            mock_dna.min_rider_rating = 1.0
            accepted = agent.receive_offer({"trip_id": "trip_456", "surge_multiplier": 1.0})

        assert not accepted
        # Repositioning process should still be the same
        assert agent._reposition_process is reposition_process


@pytest.mark.unit
class TestGoOfflineRepositioning:
    def test_go_offline_teleports_to_home(self, simpy_env, dna_factory, mock_kafka_producer):
        """Going offline should teleport driver to home_location."""
        home = (-23.56, -46.65)
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, home_location=home)
        agent.go_online()
        agent.update_location(-23.30, -46.40)  # Far from home

        agent.go_offline()

        assert agent.location == home
        assert agent.status == "offline"

    def test_go_offline_interrupts_repositioning(
        self, simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client
    ):
        """Going offline should interrupt active repositioning and teleport home."""
        home = (-23.56, -46.65)
        agent = _make_driver(
            simpy_env, dna_factory, mock_kafka_producer, mock_osrm_client, home_location=home
        )
        agent.go_online()
        agent.update_location(-23.30, -46.40)

        trip = Mock()
        agent.on_trip_completed(trip)
        simpy_env.run(until=simpy_env.now + 10)

        assert agent._reposition_process is not None
        assert agent._reposition_process.is_alive

        agent.go_offline()

        assert agent._reposition_process is None
        assert agent.location == home
        assert agent.status == "offline"

    def test_go_offline_without_repositioning_still_teleports(
        self, simpy_env, dna_factory, mock_kafka_producer
    ):
        """Going offline without repositioning should still teleport home."""
        home = (-23.56, -46.65)
        agent = _make_driver(simpy_env, dna_factory, mock_kafka_producer, home_location=home)
        agent.go_online()
        agent.update_location(-23.40, -46.50)

        agent.go_offline()

        assert agent.location == home
