import random
from unittest.mock import Mock

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def driver_agent(simpy_env, dna_factory, mock_kafka_producer):
    dna = dna_factory.driver_dna(
        response_time=5.0,
        acceptance_rate=0.8,
        min_rider_rating=4.0,
        surge_acceptance_modifier=1.5,
    )
    agent = DriverAgent(
        driver_id="driver_001",
        dna=dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.55, -46.63)
    agent.go_online()
    mock_kafka_producer.reset_mock()
    return agent


@pytest.fixture
def offer():
    return {
        "trip_id": "trip_001",
        "rider_id": "rider_001",
        "rider_rating": 4.5,
        "pickup_location": (-23.56, -46.64),
        "destination_location": (-23.57, -46.65),
        "surge_multiplier": 1.0,
        "estimated_fare": 25.50,
    }


class TestDriverResponseTime:
    def test_driver_response_time(self, simpy_env, driver_agent, offer):
        def test_process():
            result = yield simpy_env.process(driver_agent.process_ride_offer(offer))
            assert simpy_env.now >= 3.0
            assert simpy_env.now <= 7.0
            assert result in (True, False)

        simpy_env.process(test_process())
        simpy_env.run()

    def test_driver_response_time_variance(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(response_time=8.0, acceptance_rate=1.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        response_times = []

        def collect_times():
            for i in range(10):
                start_time = simpy_env.now
                yield simpy_env.process(agent.process_ride_offer({**offer, "trip_id": f"trip_{i}"}))
                response_times.append(simpy_env.now - start_time)

        simpy_env.process(collect_times())
        simpy_env.run()

        assert min(response_times) >= 6.0
        assert max(response_times) <= 10.0


class TestDriverAcceptanceProbability:
    def test_driver_acceptance_probability(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(acceptance_rate=0.8, response_time=3.0, min_rider_rating=3.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert 70 <= acceptances <= 90

    def test_driver_acceptance_surge_modifier(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(
            acceptance_rate=0.5,
            response_time=3.0,
            min_rider_rating=3.0,
            surge_acceptance_modifier=1.5,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        surge_offer = {**offer, "surge_multiplier": 2.0}
        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**surge_offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert acceptances > 50

    def test_driver_acceptance_no_surge(self, simpy_env, dna_factory, mock_kafka_producer, offer):
        random.seed(42)
        dna = dna_factory.driver_dna(acceptance_rate=0.7, response_time=3.0, min_rider_rating=3.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert 60 <= acceptances <= 80


class TestDriverRiderRatingThreshold:
    def test_driver_reject_low_rated_rider(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(
            acceptance_rate=0.8,
            response_time=3.0,
            min_rider_rating=4.0,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        low_rating_offer = {**offer, "rider_rating": 3.0}
        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**low_rating_offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert acceptances < 70

    def test_driver_accept_high_rated_rider(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(acceptance_rate=1.0, response_time=3.0, min_rider_rating=4.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        high_rating_offer = {**offer, "rider_rating": 4.8}

        def test_process():
            result = yield simpy_env.process(agent.process_ride_offer(high_rating_offer))
            assert result is True

        simpy_env.process(test_process())
        simpy_env.run()

    def test_driver_reduced_acceptance_below_threshold(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(
            acceptance_rate=1.0,
            response_time=3.0,
            min_rider_rating=4.0,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        below_threshold_offer = {**offer, "rider_rating": 3.8}
        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**below_threshold_offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert acceptances < 100


class TestDriverResponseTransitions:
    def test_driver_response_accept_transition(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(acceptance_rate=1.0, response_time=3.0, min_rider_rating=3.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()
        mock_kafka_producer.reset_mock()

        def test_process():
            result = yield simpy_env.process(agent.process_ride_offer(offer))
            assert result is True
            assert agent.status == "en_route_pickup"
            assert agent.active_trip == "trip_001"

        simpy_env.process(test_process())
        simpy_env.run()

    def test_driver_response_reject_return(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(acceptance_rate=0.0, response_time=3.0, min_rider_rating=3.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        def test_process():
            result = yield simpy_env.process(agent.process_ride_offer(offer))
            assert result is False
            assert agent.status == "online"
            assert agent.active_trip is None

        simpy_env.process(test_process())
        simpy_env.run()


class TestDriverResponseTimeout:
    def test_driver_response_timeout_compliance(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        dna = dna_factory.driver_dna(response_time=12.0)
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        def test_process():
            start_time = simpy_env.now
            yield simpy_env.process(agent.process_ride_offer(offer))
            response_time = simpy_env.now - start_time
            assert response_time < 15.0

        simpy_env.process(test_process())
        simpy_env.run()


class TestDriverSurgeAcceptanceCalculation:
    def test_driver_surge_acceptance_modifier_calculation(
        self, simpy_env, dna_factory, mock_kafka_producer, offer
    ):
        random.seed(42)
        dna = dna_factory.driver_dna(
            acceptance_rate=0.6,
            response_time=3.0,
            min_rider_rating=3.0,
            surge_acceptance_modifier=1.3,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        surge_offer = {**offer, "surge_multiplier": 3.0}
        acceptances = 0

        def process_offers():
            nonlocal acceptances
            for i in range(100):
                result = yield simpy_env.process(
                    agent.process_ride_offer({**surge_offer, "trip_id": f"trip_{i}"})
                )
                if result:
                    acceptances += 1
                    agent.complete_trip()

        simpy_env.process(process_offers())
        simpy_env.run()

        assert acceptances > 60
