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
    def test_driver_shift_starts(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test that driver goes online at shift start.

        Start simulation at 5:00 AM so morning shift (6-10 AM) starts quickly.
        """
        env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        env.process(agent.run())
        env.run(until=env.now + 6 * 3600)  # Run for 6 hours (until 11:00)

        assert agent.status == "online"

        calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver_status"
        ]
        assert len(calls) > 0

        # The value is now a DriverStatusEvent Pydantic model
        event = calls[0].kwargs["value"]
        assert event.new_status == "online"

    def test_driver_shift_ends(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test that driver goes offline after shift ends.

        Start at 6:00 AM with a 4-hour shift, should end by 10:00-11:00 AM.
        """
        env = simpy.Environment(initial_time=6 * 3600)  # Start at 6:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=4,  # Short shift for faster test
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        env.process(agent.run())
        env.run(until=env.now + 8 * 3600)  # Run for 8 hours (until 14:00)

        assert agent.status == "offline"

    def test_driver_shift_timing_randomized(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test that shift start times vary between drivers.

        Uses 3 agents starting at 5:00 AM to catch morning shifts quickly.
        """
        import random

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )

        start_times = []
        for i in range(3):
            random.seed(i * 100)
            env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00
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
                    yield env_ref.timeout(60)
                    if agent_ref.status == "online" and start_hour is None:
                        start_hour = env_ref.now

            env.process(agent.run())
            env.process(track_start_time(env, agent))
            env.run(until=env.now + 6 * 3600)  # Run until 11:00

            if start_hour is not None:
                start_times.append(start_hour)

            mock_kafka_producer.reset_mock()

        assert len(start_times) >= 2
        # Different seeds should produce different start times
        assert len(set(start_times)) > 1

    def test_driver_shift_respects_days_per_week(
        self, mock_kafka_producer, dna_factory: DNAFactory
    ):
        """Test that days_per_week=7 results in driver going online.

        Start at 5:00 AM to catch morning shift quickly.
        """
        env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,  # Always work
            avg_hours_per_day=4,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        env.process(agent.run())
        env.run(until=env.now + 6 * 3600)  # Run until 11:00

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver_status"
        ]

        # The value is now a DriverStatusEvent Pydantic model
        online_events = [
            call for call in status_calls if "online" in call.kwargs["value"].new_status
        ]

        # With avg_days_per_week=7, driver should go online on day 1
        assert len(online_events) >= 1

    def test_driver_shift_interruption_during_trip(
        self, mock_kafka_producer, dna_factory: DNAFactory
    ):
        """Test driver completes trip before going offline."""
        env = simpy.Environment(initial_time=6 * 3600)  # Start at 6:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=2,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        def assign_trip_near_shift_end():
            yield env.timeout(1.5 * 3600)  # At 7:30
            if agent.status == "online":
                agent.accept_trip("trip_001")
                yield env.timeout(0.5 * 3600)  # 30 min trip
                agent.complete_trip()

        env.process(agent.run())
        env.process(assign_trip_near_shift_end())
        env.run(until=env.now + 4 * 3600)  # Run until 10:00

        assert agent.status == "offline"
        assert agent.active_trip is None

    def test_driver_shift_status_event_online(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test online status event is emitted."""
        env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        env.process(agent.run())
        env.run(until=env.now + 6 * 3600)  # Run until 11:00

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver_status"
        ]
        assert len(status_calls) > 0

        # The value is now a DriverStatusEvent Pydantic model
        event = status_calls[0].kwargs["value"]
        assert event.new_status == "online"
        assert event.driver_id == "driver_001"

    def test_driver_shift_status_event_offline(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test offline status event is emitted after shift ends."""
        env = simpy.Environment(initial_time=6 * 3600)  # Start at 6:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=2,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        env.process(agent.run())
        env.run(until=env.now + 5 * 3600)  # Run until 11:00

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver_status"
        ]

        # The value is now a DriverStatusEvent Pydantic model
        offline_events = [
            call for call in status_calls if call.kwargs["value"].new_status == "offline"
        ]
        assert len(offline_events) > 0

    def test_driver_shift_duration_exact(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test that shift duration matches avg_hours_per_day."""
        env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=4,  # Shorter shift for faster test
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        times = {}

        def track_time():
            while True:
                yield env.timeout(60)
                if agent.status == "online" and "online" not in times:
                    times["online"] = env.now
                elif agent.status == "offline" and "online" in times and "offline" not in times:
                    times["offline"] = env.now

        env.process(agent.run())
        env.process(track_time())
        env.run(until=env.now + 8 * 3600)  # Run until 13:00

        if "online" in times and "offline" in times:
            duration = (times["offline"] - times["online"]) / 3600
            assert 3.5 <= duration <= 4.5

    def test_driver_shift_preference_morning(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test morning shift starts in morning hours."""
        env = simpy.Environment(initial_time=5 * 3600)  # Start at 5:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.MORNING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        start_hour = None

        def track_start_time():
            nonlocal start_hour
            while True:
                yield env.timeout(60)
                if agent.status == "online" and start_hour is None:
                    start_hour = (env.now % (24 * 3600)) / 3600

        env.process(agent.run())
        env.process(track_start_time())
        env.run(until=env.now + 6 * 3600)  # Run until 11:00

        assert start_hour is not None
        assert 5.5 <= start_hour <= 10.5

    def test_driver_shift_preference_evening(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test evening shift starts in evening hours.

        Start simulation at 15:00 so we only need to wait ~6 hours for evening shift.
        """
        # Start at 15:00 (54000 seconds into the day)
        env = simpy.Environment(initial_time=15 * 3600)

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.EVENING,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        start_hour = None

        def track_start_time():
            nonlocal start_hour
            while True:
                yield env.timeout(60)  # Check every 60s, not 1s
                if agent.status == "online" and start_hour is None:
                    start_hour = (env.now % (24 * 3600)) / 3600

        env.process(agent.run())
        env.process(track_start_time())
        env.run(until=env.now + 8 * 3600)  # 8 hours from 15:00 = until 23:00

        assert start_hour is not None
        assert 16.5 <= start_hour <= 21.5

    def test_driver_shift_preference_flexible(self, mock_kafka_producer, dna_factory: DNAFactory):
        """Test flexible shift can start at any hour.

        Flexible shifts have a random start time, so we just verify
        the driver eventually goes online.
        """
        env = simpy.Environment(initial_time=6 * 3600)  # Start at 6:00

        dna = dna_factory.driver_dna(
            shift_preference=ShiftPreference.FLEXIBLE,
            avg_days_per_week=7,
        )
        agent = DriverAgent(
            driver_id="driver_001",
            dna=dna,
            env=env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        mock_kafka_producer.reset_mock()

        env.process(agent.run())
        env.run(until=env.now + 6 * 3600)  # Run for 6 hours

        status_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call.kwargs.get("topic") == "driver_status"
        ]

        # Flexible driver should go online at some point
        # The value is now a DriverStatusEvent Pydantic model
        online_events = [
            call for call in status_calls if call.kwargs["value"].new_status == "online"
        ]
        assert len(online_events) >= 1
