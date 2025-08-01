import random
from unittest.mock import Mock

import pytest
import simpy

from agents.dna import RiderDNA
from agents.rider_agent import RiderAgent


@pytest.fixture
def rider_dna():
    return RiderDNA(
        behavior_factor=0.7,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=5,
        frequent_destinations=[
            {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.6},
            {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            {"name": "mall", "coordinates": (-23.55, -46.64), "weight": 0.1},
        ],
        home_location=(-23.55, -46.63),
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
        phone="+5511888888888",
        payment_method_type="credit_card",
        payment_method_masked="**** **** **** 1234",
    )


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


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

    def test_rider_initial_state(self, rider_agent):
        assert rider_agent.status == "idle"
        assert rider_agent.location is None
        assert rider_agent.active_trip is None
        assert rider_agent.current_rating == 5.0
        assert rider_agent.rating_count == 0


class TestRiderDNAImmutability:
    def test_rider_dna_immutability(self, rider_agent, rider_dna):
        original_behavior = rider_dna.behavior_factor
        with pytest.raises(AttributeError):
            rider_agent.dna = RiderDNA(
                behavior_factor=0.3,
                patience_threshold=200,
                max_surge_multiplier=1.5,
                avg_rides_per_week=3,
                frequent_destinations=[
                    {"name": "office", "coordinates": (-23.56, -46.65), "weight": 0.5},
                    {"name": "home", "coordinates": (-23.55, -46.63), "weight": 0.5},
                ],
                home_location=(-23.55, -46.63),
                first_name="Ana",
                last_name="Costa",
                email="ana@example.com",
                phone="+5511777777777",
                payment_method_type="debit_card",
                payment_method_masked="**** **** **** 5678",
            )
        assert rider_agent.dna.behavior_factor == original_behavior


class TestRiderStatusTransitions:
    def test_rider_status_transition_idle_to_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        assert rider_agent.active_trip == "trip_001"

    def test_rider_status_transition_waiting_to_in_trip(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        assert rider_agent.status == "in_trip"

    def test_rider_status_transition_in_trip_to_idle(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        rider_agent.complete_trip()
        assert rider_agent.status == "idle"
        assert rider_agent.active_trip is None

    def test_rider_cancel_while_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        rider_agent.cancel_trip()
        assert rider_agent.status == "idle"
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

        selected_coords = []
        for _ in range(100):
            coords = rider_agent.select_destination()
            selected_coords.append(coords)

        valid_coords = [d["coordinates"] for d in rider_dna.frequent_destinations]
        for coords in selected_coords:
            assert tuple(coords) in [tuple(c) for c in valid_coords]

        work_coords = (-23.56, -46.65)
        work_count = sum(1 for c in selected_coords if tuple(c) == work_coords)
        # With weight 0.6, expect roughly 60 out of 100
        assert 40 < work_count < 80
