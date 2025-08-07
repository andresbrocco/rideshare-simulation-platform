import random

import pytest
import simpy

from src.agents.dna import RiderDNA, haversine_distance
from src.agents.rider_agent import RiderAgent
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def dna_factory():
    return DNAFactory(seed=42)


class TestDestinationFromHome:
    def test_destination_from_home_frequent(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        selections = []
        for _ in range(100):
            dest = agent.select_destination()
            selections.append(dest)

        valid_frequent = [tuple(d["coordinates"]) for d in dna.frequent_destinations]
        frequent_count = sum(1 for d in selections if d in valid_frequent)

        assert frequent_count > 70

    def test_destination_from_home_random(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        selections = []
        for _ in range(100):
            dest = agent.select_destination()
            selections.append(dest)

        valid_frequent = [tuple(d["coordinates"]) for d in dna.frequent_destinations]
        random_count = sum(1 for d in selections if d not in valid_frequent)

        assert random_count > 10


class TestDestinationFromNonHome:
    def test_destination_from_nonhome_return_home(
        self, simpy_env, dna_factory, mock_kafka_producer
    ):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.56, -46.65)

        selections = []
        for _ in range(100):
            dest = agent.select_destination()
            selections.append(dest)

        home_count = sum(1 for d in selections if d == home)

        assert home_count > 50

    def test_destination_from_nonhome_frequent(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.56, -46.65)

        selections = []
        for _ in range(100):
            dest = agent.select_destination()
            selections.append(dest)

        valid_frequent = [tuple(d["coordinates"]) for d in dna.frequent_destinations]
        frequent_count = sum(1 for d in selections if d in valid_frequent and d != home)

        assert frequent_count > 20

    def test_destination_from_nonhome_random(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.56, -46.65)

        selections = []
        for _ in range(100):
            dest = agent.select_destination()
            selections.append(dest)

        valid_frequent = [tuple(d["coordinates"]) for d in dna.frequent_destinations]
        random_count = sum(1 for d in selections if d not in valid_frequent and d != home)

        assert random_count > 5


class TestDestinationWeightedSelection:
    def test_destination_weighted_selection(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
                {"name": "mall", "coordinates": (-23.555, -46.64), "weight": 0.2},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        work_coords = (-23.56, -46.65)
        gym_coords = (-23.54, -46.62)
        mall_coords = (-23.555, -46.64)

        work_count = 0
        gym_count = 0
        mall_count = 0

        for _ in range(500):
            dest = agent.select_destination()
            if dest == work_coords:
                work_count += 1
            elif dest == gym_coords:
                gym_count += 1
            elif dest == mall_coords:
                mall_count += 1

        total_frequent = work_count + gym_count + mall_count
        if total_frequent > 0:
            work_ratio = work_count / total_frequent
            gym_ratio = gym_count / total_frequent
            mall_ratio = mall_count / total_frequent

            assert pytest.approx(work_ratio, abs=0.1) == 0.5
            assert pytest.approx(gym_ratio, abs=0.1) == 0.3
            assert pytest.approx(mall_ratio, abs=0.1) == 0.2


class TestDestinationTimeAffinity:
    def test_destination_time_affinity_match(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {
                    "name": "work",
                    "coordinates": (-23.56, -46.65),
                    "weight": 0.3,
                    "time_affinity": [8, 9, 17, 18],
                },
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        simpy_env.run(until=8 * 3600)

        work_coords = (-23.56, -46.65)
        gym_coords = (-23.54, -46.62)

        work_count = 0
        gym_count = 0

        for _ in range(300):
            dest = agent.select_destination()
            if dest == work_coords:
                work_count += 1
            elif dest == gym_coords:
                gym_count += 1

        total_frequent = work_count + gym_count
        if total_frequent > 0:
            work_ratio = work_count / total_frequent

            assert work_ratio > 0.5

    def test_destination_time_affinity_no_match(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {
                    "name": "work",
                    "coordinates": (-23.56, -46.65),
                    "weight": 0.3,
                    "time_affinity": [8, 9, 17, 18],
                },
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.3},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        simpy_env.run(until=14 * 3600)

        work_coords = (-23.56, -46.65)
        gym_coords = (-23.54, -46.62)

        work_count = 0
        gym_count = 0

        for _ in range(300):
            dest = agent.select_destination()
            if dest == work_coords:
                work_count += 1
            elif dest == gym_coords:
                gym_count += 1

        total_frequent = work_count + gym_count
        if total_frequent > 0:
            work_ratio = work_count / total_frequent

            assert pytest.approx(work_ratio, abs=0.15) == 0.5


class TestDestinationWeightNormalization:
    def test_destination_weight_normalization(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.6},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.4},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        work_coords = (-23.56, -46.65)
        gym_coords = (-23.54, -46.62)

        work_count = 0
        gym_count = 0

        for _ in range(400):
            dest = agent.select_destination()
            if dest == work_coords:
                work_count += 1
            elif dest == gym_coords:
                gym_count += 1

        total_frequent = work_count + gym_count
        if total_frequent > 0:
            work_ratio = work_count / total_frequent
            gym_ratio = gym_count / total_frequent

            assert pytest.approx(work_ratio, abs=0.1) == 0.6
            assert pytest.approx(gym_ratio, abs=0.1) == 0.4


class TestDestinationRandomBounds:
    def test_destination_random_within_bounds(self, simpy_env, dna_factory, mock_kafka_producer):
        random.seed(42)

        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(
            home_location=home,
            frequent_destinations=[
                {"name": "work", "coordinates": (-23.56, -46.65), "weight": 0.5},
                {"name": "gym", "coordinates": (-23.54, -46.62), "weight": 0.5},
            ],
        )

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*home)

        random_locations = []
        valid_frequent = [tuple(d["coordinates"]) for d in dna.frequent_destinations]

        for _ in range(200):
            dest = agent.select_destination()
            if dest not in valid_frequent:
                random_locations.append(dest)

        for lat, lon in random_locations:
            assert -23.80 <= lat <= -23.35
            assert -46.85 <= lon <= -46.35


class TestDestinationReturnType:
    def test_destination_returns_coordinates(self, simpy_env, dna_factory, mock_kafka_producer):
        dna = dna_factory.rider_dna()

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(*dna.home_location)

        dest = agent.select_destination()

        assert isinstance(dest, tuple)
        assert len(dest) == 2
        assert isinstance(dest[0], float)
        assert isinstance(dest[1], float)


class TestDestinationHomeDetection:
    def test_destination_home_detection(self, simpy_env, dna_factory, mock_kafka_producer):
        home = (-23.55, -46.63)
        dna = dna_factory.rider_dna(home_location=home)

        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        agent.update_location(*home)
        distance = haversine_distance(home[0], home[1], agent.location[0], agent.location[1])
        assert distance < 0.1

        agent.update_location(-23.56, -46.65)
        distance = haversine_distance(home[0], home[1], agent.location[0], agent.location[1])
        assert distance > 0.1
