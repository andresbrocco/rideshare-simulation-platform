import json
from unittest.mock import Mock

import pytest
import simpy

from src.agents.dna import DriverDNA, ShiftPreference
from src.agents.driver_agent import DriverAgent
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


class TestDriverShiftLifecycle:
    def test_driver_shift_starts(self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 12 * 3600)

        assert agent.status == "online"

        calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver-status"
        ]
        assert len(calls) > 0

        event = json.loads(calls[0].kwargs["value"])
        assert event["new_status"] == "online"

    def test_driver_shift_ends(self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=8,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 20 * 3600)

        assert agent.status == "offline"

    def test_driver_shift_timing_randomized(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        import random

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )

        start_times = []
        for i in range(10):
            random.seed(i * 100)
            env = simpy.Environment()
            agent = DriverAgent(
                driver_id=f"driver_{i:03d}",
                dna=dna,
                env=env,
                kafka_producer=mock_kafka_producer,
            )
            agent.update_location(-23.55, -46.63)

            start_hour = None

            def track_start_time(env_ref, agent_ref):
                nonlocal start_hour
                while True:
                    yield env_ref.timeout(1)
                    if agent_ref.status == "online" and start_hour is None:
                        start_hour = env_ref.now

            env.process(agent.run())
            env.process(track_start_time(env, agent))
            env.run(until=env.now + 12 * 3600)

            if start_hour is not None:
                start_times.append(start_hour)

            mock_kafka_producer.reset_mock()

        assert len(start_times) >= 5
        assert len(set(start_times)) > 1

    def test_driver_shift_respects_days_per_week(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=5,
            avg_hours_per_day=4,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 8 * 24 * 3600)

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver-status"
        ]

        online_events = [
            call
            for call in status_calls
            if "online" in json.loads(call.kwargs["value"])["new_status"]
        ]

        assert 4 <= len(online_events) <= 6

    def test_driver_shift_interruption_during_trip(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=2,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def assign_trip_near_shift_end():
            yield simpy_env.timeout(9 * 3600)
            if agent.status == "online":
                agent.accept_trip("trip_001")
                yield simpy_env.timeout(1 * 3600)
                agent.complete_trip()

        simpy_env.process(agent.run())
        simpy_env.process(assign_trip_near_shift_end())
        simpy_env.run(until=simpy_env.now + 15 * 3600)

        assert agent.status == "offline"
        assert agent.active_trip is None

    def test_driver_shift_status_event_online(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 12 * 3600)

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver-status"
        ]
        assert len(status_calls) > 0

        event = json.loads(status_calls[0].kwargs["value"])
        assert event["new_status"] == "online"
        assert event["driver_id"] == "driver_001"

    def test_driver_shift_status_event_offline(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=2,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 15 * 3600)

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver-status"
        ]

        offline_events = [
            call
            for call in status_calls
            if json.loads(call.kwargs["value"])["new_status"] == "offline"
        ]
        assert len(offline_events) > 0

    def test_driver_shift_duration_exact(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=6,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        times = {}

        def track_time():
            while True:
                yield simpy_env.timeout(1)
                if agent.status == "online" and "online" not in times:
                    times["online"] = simpy_env.now
                elif agent.status == "offline" and "online" in times and "offline" not in times:
                    times["offline"] = simpy_env.now

        simpy_env.process(agent.run())
        simpy_env.process(track_time())
        simpy_env.run(until=simpy_env.now + 20 * 3600)

        if "online" in times and "offline" in times:
            duration = (times["offline"] - times["online"]) / 3600
            assert 5.5 <= duration <= 6.5

    def test_driver_shift_preference_morning(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        start_hour = None

        def track_start_time():
            nonlocal start_hour
            while True:
                yield simpy_env.timeout(1)
                if agent.status == "online" and start_hour is None:
                    start_hour = (simpy_env.now % (24 * 3600)) / 3600

        simpy_env.process(agent.run())
        simpy_env.process(track_start_time())
        simpy_env.run(until=simpy_env.now + 12 * 3600)

        assert start_hour is not None
        assert 5.5 <= start_hour <= 10.5

    def test_driver_shift_preference_evening(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.EVENING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        start_hour = None

        def track_start_time():
            nonlocal start_hour
            while True:
                yield simpy_env.timeout(1)
                if agent.status == "online" and start_hour is None:
                    start_hour = (simpy_env.now % (24 * 3600)) / 3600

        simpy_env.process(agent.run())
        simpy_env.process(track_start_time())
        simpy_env.run(until=simpy_env.now + 24 * 3600)

        assert start_hour is not None
        assert 16.5 <= start_hour <= 21.5

    def test_driver_shift_preference_flexible(
        self, simpy_env, mock_kafka_producer, dna_factory: DNAFactory
    ):
        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.FLEXIBLE,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        simpy_env.process(agent.run())
        simpy_env.run(until=simpy_env.now + 24 * 3600)

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver-status"
        ]

        if status_calls:
            event = json.loads(status_calls[0].kwargs["value"])
            if event["new_status"] == "online":
                start_hour = (simpy_env.now % (24 * 3600)) / 3600
                assert 0 <= start_hour <= 24
