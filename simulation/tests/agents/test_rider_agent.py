import random
from unittest.mock import Mock

import pytest
import simpy

from agents.dna import RiderDNA
from agents.rider_agent import RiderAgent
from tests.factories import DNAFactory


@pytest.fixture
def rider_dna(dna_factory: DNAFactory):
    # All coordinates must be inside sample zones (PIN, BVI, SEE)
    return dna_factory.rider_dna(
        frequent_destinations=[
            {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.6},  # Inside BVI
            {"name": "gym", "coordinates": (-23.565, -46.695), "weight": 0.3},  # Inside PIN
            {"name": "mall", "coordinates": (-23.55, -46.635), "weight": 0.1},  # Inside SEE
        ],
    )


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def rider_agent(simpy_env, rider_dna, mock_kafka_producer):
    return RiderAgent(
        rider_id="rider_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )


class TestRiderAgentInit:
    def test_rider_agent_init(self, simpy_env, rider_dna, mock_kafka_producer):
        agent = RiderAgent(
            rider_id="rider_001",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        assert agent.rider_id == "rider_001"
        assert agent.dna == rider_dna

    def test_rider_initial_state(self, rider_agent, rider_dna):
        assert rider_agent.status == "offline"
        # Location is now set from DNA home_location on creation
        assert rider_agent.location == rider_dna.home_location
        assert rider_agent.active_trip is None
        assert rider_agent.current_rating == 5.0
        assert rider_agent.rating_count == 0


class TestRiderDNAImmutability:
    def test_rider_dna_immutability(self, rider_agent, rider_dna, dna_factory: DNAFactory):
        original_behavior = rider_dna.behavior_factor
        with pytest.raises(AttributeError):
            rider_agent.dna = dna_factory.rider_dna(
                behavior_factor=0.3,
                patience_threshold=200,
            )
        assert rider_agent.dna.behavior_factor == original_behavior


class TestRiderStatusTransitions:
    def test_rider_status_transition_offline_to_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        assert rider_agent.active_trip == "trip_001"

    def test_rider_status_transition_waiting_to_in_trip(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        assert rider_agent.status == "in_trip"

    def test_rider_status_transition_in_trip_to_offline(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        rider_agent.complete_trip()
        assert rider_agent.status == "offline"
        assert rider_agent.active_trip is None

    def test_rider_cancel_while_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        rider_agent.cancel_trip()
        assert rider_agent.status == "offline"
        assert rider_agent.active_trip is None


class TestRiderStateManagement:
    def test_rider_location_update(self, rider_agent):
        rider_agent.update_location(-23.55, -46.63)
        assert rider_agent.location == (-23.55, -46.63)

    def test_rider_rating_update(self, rider_agent):
        assert rider_agent.current_rating == 5.0
        assert rider_agent.rating_count == 0

        rider_agent.update_rating(3)
        # (5.0 * 0 + 3) / 1 = 3.0
        assert rider_agent.current_rating == 3.0
        assert rider_agent.rating_count == 1

        rider_agent.update_rating(5)
        # (3.0 * 1 + 5) / 2 = 4.0
        assert rider_agent.current_rating == 4.0
        assert rider_agent.rating_count == 2


class TestRiderSimpyProcess:
    def test_rider_agent_is_simpy_process(self, rider_agent, simpy_env):
        process = simpy_env.process(rider_agent.run())
        assert process is not None
        simpy_env.run(until=1)


class TestRiderDestinationSelection:
    def test_rider_frequent_destination_selection(self, rider_agent, rider_dna):
        random.seed(42)
        rider_agent.update_location(*rider_dna.home_location)

        selected_coords = []
        for _ in range(100):
            coords = rider_agent.select_destination()
            selected_coords.append(coords)

        valid_coords = [tuple(d["coordinates"]) for d in rider_dna.frequent_destinations]
        frequent_count = sum(1 for c in selected_coords if tuple(c) in valid_coords)

        # From home: expect ~80% frequent destinations
        assert frequent_count > 60


class TestRiderZoneBasedGeneration:
    """Tests for zone-based coordinate generation."""

    def test_generate_random_location_returns_in_zone_coordinates(self, rider_agent):
        """Verify _generate_random_location returns coordinates inside a zone."""
        from agents.zone_validator import is_location_in_any_zone

        # Generate multiple locations and verify all are in zones
        for _ in range(10):
            lat, lon = rider_agent._generate_random_location()
            assert is_location_in_any_zone(
                lat, lon
            ), f"Generated location ({lat}, {lon}) is not inside any zone"

    def test_select_destination_returns_valid_zone_coordinates(self, rider_agent, rider_dna):
        """Verify select_destination always returns coordinates inside a zone."""
        from agents.zone_validator import is_location_in_any_zone

        random.seed(12345)
        rider_agent.update_location(*rider_dna.home_location)

        # Test from both home and away locations
        for _ in range(50):
            lat, lon = rider_agent.select_destination()
            assert is_location_in_any_zone(
                lat, lon
            ), f"Destination ({lat}, {lon}) is not inside any zone"
