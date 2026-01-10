import json
from unittest.mock import Mock

import pytest
import simpy

from src.agents.rider_agent import RiderAgent
from src.events.schemas import TripEvent
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


class TestRiderRequestTiming:
    """Test that riders request trips based on their DNA frequency settings.

    Uses high frequency DNA to make requests happen quickly and deterministically.
    Statistical distribution testing over long periods is not appropriate for unit tests.
    """

    def test_rider_makes_multiple_requests(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        """Verify rider makes multiple requests when frequency is high.

        Uses minimum patience threshold (120s) so the rider times out
        and goes back to requesting, allowing multiple request cycles.
        """
        # High frequency (~6s intervals) + min patience (120s) = ~126s per cycle
        dna = dna_factory.rider_dna(avg_rides_per_week=100000, patience_threshold=120)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        simpy_env.process(agent.run())
        simpy_env.run(until=300)  # 5 minutes of simulation time

        # Count trip.requested events emitted to Kafka
        trip_requests = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "trips"
            and "trip.requested" in call.kwargs.get("value", "")
        ]

        # With ~6s wait + 120s patience timeout = ~126s per cycle
        # In 300 seconds, expect at least 2 complete request cycles
        assert len(trip_requests) >= 2


class TestRiderRequestCreatesTrip:
    def test_rider_request_creates_trip(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def verify_request():
            yield simpy_env.timeout(10)
            assert agent.status == "waiting"
            assert agent.active_trip is not None

        simpy_env.process(agent.run())
        simpy_env.process(verify_request())
        simpy_env.run(until=20)


class TestRiderPatienceTimeout:
    def test_rider_patience_timeout(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000, patience_threshold=180)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        first_trip = None
        cancelled = False

        def track_cancellation():
            nonlocal first_trip, cancelled
            yield simpy_env.timeout(10)
            first_trip = agent.active_trip

            yield simpy_env.timeout(185)
            if first_trip and agent.active_trip != first_trip:
                cancelled = True

        simpy_env.process(agent.run())
        simpy_env.process(track_cancellation())
        simpy_env.run(until=200)

        assert cancelled

    def test_rider_patience_timeout_event(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000, patience_threshold=180)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        simpy_env.process(agent.run())
        simpy_env.run(until=300)

        trip_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "trips"
        ]

        cancelled_events = [
            call
            for call in trip_calls
            if "trip.cancelled" in json.loads(call.kwargs["value"])["event_type"]
        ]

        assert len(cancelled_events) > 0
        event = json.loads(cancelled_events[0].kwargs["value"])
        assert event["cancelled_by"] == "rider"
        assert event["cancellation_reason"] == "patience_timeout"


class TestRiderMatchAccepted:
    def test_rider_match_accepted(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        match_event = simpy.Event(simpy_env)

        def provide_match():
            yield simpy_env.timeout(12)
            agent.start_trip()
            match_event.succeed()

        def verify_match():
            yield simpy_env.timeout(15)
            assert agent.status == "in_trip"

        simpy_env.process(agent.run())
        simpy_env.process(provide_match())
        simpy_env.process(verify_match())
        simpy_env.run(until=20)

    def test_rider_wait_for_pickup(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def simulate_match():
            yield simpy_env.timeout(10)
            assert agent.status == "waiting"
            agent.start_trip()
            yield simpy_env.timeout(30)
            assert agent.status == "in_trip"

        simpy_env.process(agent.run())
        simpy_env.process(simulate_match())
        simpy_env.run(until=50)

    def test_rider_board_vehicle(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def driver_arrives():
            yield simpy_env.timeout(10)
            agent.start_trip()
            yield simpy_env.timeout(1)
            assert agent.status == "in_trip"

        simpy_env.process(agent.run())
        simpy_env.process(driver_arrives())
        simpy_env.run(until=20)


class TestRiderTripCompletion:
    def test_rider_trip_completion(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(avg_rides_per_week=100000)
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def complete_trip_flow():
            yield simpy_env.timeout(10)
            original_location = agent.location
            agent.start_trip()
            yield simpy_env.timeout(10)
            destination = agent.select_destination()
            agent.update_location(destination[0], destination[1])
            agent.complete_trip()
            yield simpy_env.timeout(1)
            assert agent.status == "offline"
            assert agent.active_trip is None
            assert agent.location != original_location

        simpy_env.process(agent.run())
        simpy_env.process(complete_trip_flow())
        simpy_env.run(until=50)

    def test_rider_location_update_after_trip(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.rider_dna(
            avg_rides_per_week=100000,
            frequent_destinations=[
                {"coordinates": (-23.56, -46.65), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4},
            ],
        )
        agent = RiderAgent(
            rider_id="rider_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def complete_trip_to_destination():
            yield simpy_env.timeout(10)
            agent.start_trip()
            yield simpy_env.timeout(10)
            destination = (-23.56, -46.65)
            agent.update_location(destination[0], destination[1])
            agent.complete_trip()
            yield simpy_env.timeout(1)
            assert agent.location == destination

        simpy_env.process(agent.run())
        simpy_env.process(complete_trip_to_destination())
        simpy_env.run(until=50)
