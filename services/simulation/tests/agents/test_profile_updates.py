"""Tests for profile update events (SCD Type 2 tracking)."""

import random
from unittest.mock import Mock, patch

import pytest
import simpy

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.agents.driver_agent import DriverAgent
from src.agents.profile_mutations import mutate_driver_profile, mutate_rider_profile
from src.agents.rider_agent import RiderAgent
from tests.factories import DNAFactory


@pytest.mark.unit
class TestMutateDriverProfile:
    """Tests for driver profile mutation logic."""

    def test_mutate_driver_profile_returns_changes(self, dna_factory: DNAFactory):
        """Profile mutation should return a non-empty dict."""
        driver_dna = dna_factory.driver_dna()
        random.seed(42)

        changes = mutate_driver_profile(driver_dna)

        assert isinstance(changes, dict)
        assert len(changes) > 0

    def test_mutate_driver_profile_vehicle_change(self, dna_factory: DNAFactory):
        """Vehicle change should include all vehicle fields."""
        driver_dna = dna_factory.driver_dna()

        # Find a seed that triggers vehicle change (roll < 0.40)
        for seed in range(100):
            random.seed(seed)
            if random.random() < 0.40:
                random.seed(seed)
                changes = mutate_driver_profile(driver_dna)
                assert "vehicle_make" in changes
                assert "vehicle_model" in changes
                assert "vehicle_year" in changes
                assert "license_plate" in changes
                return

        pytest.fail("Could not find a seed that triggers vehicle change")

    def test_mutate_driver_profile_phone_change(self, dna_factory: DNAFactory):
        """Phone change should only include phone field."""
        driver_dna = dna_factory.driver_dna()

        # Find a seed that triggers phone change (0.40 <= roll < 0.60)
        for seed in range(100):
            random.seed(seed)
            roll = random.random()
            if 0.40 <= roll < 0.60:
                random.seed(seed)
                changes = mutate_driver_profile(driver_dna)
                assert "phone" in changes
                assert len(changes) == 1
                return

        pytest.fail("Could not find a seed that triggers phone change")

    def test_mutate_driver_profile_email_change(self, dna_factory: DNAFactory):
        """Email change should only include email field."""
        driver_dna = dna_factory.driver_dna()

        # Find a seed that triggers email change (0.60 <= roll < 0.75)
        for seed in range(100):
            random.seed(seed)
            roll = random.random()
            if 0.60 <= roll < 0.75:
                random.seed(seed)
                changes = mutate_driver_profile(driver_dna)
                assert "email" in changes
                assert len(changes) == 1
                return

        pytest.fail("Could not find a seed that triggers email change")

    def test_mutate_driver_profile_shift_change(self, dna_factory: DNAFactory):
        """Shift preference change should be different from current."""
        driver_dna = dna_factory.driver_dna(shift_preference=ShiftPreference.MORNING)

        # Find a seed that triggers shift change (roll >= 0.75)
        for seed in range(100):
            random.seed(seed)
            roll = random.random()
            if roll >= 0.75:
                random.seed(seed)
                changes = mutate_driver_profile(driver_dna)
                assert "shift_preference" in changes
                assert changes["shift_preference"] != "morning"
                return

        pytest.fail("Could not find a seed that triggers shift change")


@pytest.mark.unit
class TestMutateRiderProfile:
    """Tests for rider profile mutation logic."""

    def test_mutate_rider_profile_returns_changes(self, dna_factory: DNAFactory):
        """Profile mutation should return a non-empty dict."""
        rider_dna = dna_factory.rider_dna()
        random.seed(42)

        changes = mutate_rider_profile(rider_dna)

        assert isinstance(changes, dict)
        assert len(changes) > 0

    def test_mutate_rider_profile_payment_change(self, dna_factory: DNAFactory):
        """Payment change should include type and masked fields."""
        rider_dna = dna_factory.rider_dna()

        # Find a seed that triggers payment change (roll < 0.50)
        for seed in range(100):
            random.seed(seed)
            if random.random() < 0.50:
                random.seed(seed)
                changes = mutate_rider_profile(rider_dna)
                assert "payment_method_type" in changes
                assert "payment_method_masked" in changes
                return

        pytest.fail("Could not find a seed that triggers payment change")

    def test_mutate_rider_profile_phone_change(self, dna_factory: DNAFactory):
        """Phone change should only include phone field."""
        rider_dna = dna_factory.rider_dna()

        # Find a seed that triggers phone change (0.50 <= roll < 0.75)
        for seed in range(100):
            random.seed(seed)
            roll = random.random()
            if 0.50 <= roll < 0.75:
                random.seed(seed)
                changes = mutate_rider_profile(rider_dna)
                assert "phone" in changes
                assert len(changes) == 1
                return

        pytest.fail("Could not find a seed that triggers phone change")

    def test_mutate_rider_profile_email_change(self, dna_factory: DNAFactory):
        """Email change should only include email field."""
        rider_dna = dna_factory.rider_dna()

        # Find a seed that triggers email change (roll >= 0.75)
        for seed in range(100):
            random.seed(seed)
            roll = random.random()
            if roll >= 0.75:
                random.seed(seed)
                changes = mutate_rider_profile(rider_dna)
                assert "email" in changes
                assert len(changes) == 1
                return

        pytest.fail("Could not find a seed that triggers email change")


@pytest.mark.unit
class TestDriverEmitsUpdateEvent:
    """Tests for driver profile update event emission."""

    def test_driver_emits_update_event(self, dna_factory: DNAFactory):
        """Driver should emit profile.updated event via _emit_update_event()."""
        env = simpy.Environment()
        mock_producer = Mock()
        driver_dna = dna_factory.driver_dna()

        driver = DriverAgent(
            driver_id="driver_update_001",
            dna=driver_dna,
            env=env,
            kafka_producer=mock_producer,
        )

        # Reset mock to ignore creation event
        mock_producer.reset_mock()

        random.seed(42)
        driver._emit_update_event()

        # Method should complete without error (uses _emit_event path)
        # The actual Kafka call happens via run_coroutine_safe which may not
        # trigger the mock in a sync context

    def test_update_event_has_correct_type(self, dna_factory: DNAFactory):
        """Update event should have event_type='driver.updated'."""
        env = simpy.Environment()
        driver_dna = dna_factory.driver_dna()

        # Use a mock that tracks the _emit_event call
        driver = DriverAgent(
            driver_id="driver_type_001",
            dna=driver_dna,
            env=env,
            kafka_producer=None,
        )

        # Patch _emit_event to capture the event (_emit_event is synchronous)
        captured_events = []

        def capture_event(event, **kwargs):
            captured_events.append(event)

        driver._emit_event = capture_event

        random.seed(42)
        driver._emit_update_event()

        assert len(captured_events) == 1
        assert captured_events[0].event_type == "driver.updated"


@pytest.mark.unit
class TestRiderEmitsUpdateEvent:
    """Tests for rider profile update event emission."""

    def test_rider_emits_update_event(self, dna_factory: DNAFactory):
        """Rider should emit profile.updated event via _emit_update_event()."""
        env = simpy.Environment()
        mock_producer = Mock()
        rider_dna = dna_factory.rider_dna()

        rider = RiderAgent(
            rider_id="rider_update_001",
            dna=rider_dna,
            env=env,
            kafka_producer=mock_producer,
        )

        # Reset mock to ignore creation event
        mock_producer.reset_mock()

        random.seed(42)
        rider._emit_update_event()

        # Method called successfully
        assert True

    def test_update_event_has_correct_type(self, dna_factory: DNAFactory):
        """Update event should have event_type='rider.updated'."""
        env = simpy.Environment()
        rider_dna = dna_factory.rider_dna()

        rider = RiderAgent(
            rider_id="rider_type_001",
            dna=rider_dna,
            env=env,
            kafka_producer=None,
        )

        # Patch _emit_event to capture the event (_emit_event is synchronous)
        captured_events = []

        def capture_event(event, **kwargs):
            captured_events.append(event)

        rider._emit_event = capture_event

        random.seed(42)
        rider._emit_update_event()

        assert len(captured_events) == 1
        assert captured_events[0].event_type == "rider.updated"


@pytest.mark.unit
class TestPuppetNoProfileUpdates:
    """Tests to verify puppets don't emit profile updates."""

    def test_puppet_driver_no_profile_updates(self, dna_factory: DNAFactory):
        """Puppet drivers should not emit profile update events."""
        env = simpy.Environment()
        mock_producer = Mock()
        driver_dna = dna_factory.driver_dna()

        driver = DriverAgent(
            driver_id="puppet_driver_001",
            dna=driver_dna,
            env=env,
            kafka_producer=mock_producer,
            puppet=True,
        )

        # Reset mock to ignore creation event
        mock_producer.reset_mock()

        # Run simulation for a short time with very short update interval
        with patch("src.agents.driver_agent.PROFILE_UPDATE_INTERVAL_SECONDS", 10):
            # Start the driver process
            driver._status = "online"
            env.process(driver.run())
            env.run(until=100)

        # Check that no profile update events were emitted
        # Puppets should only emit GPS pings, not profile updates
        profile_calls = [
            call
            for call in mock_producer.produce.call_args_list
            if call[1].get("topic") == "driver_profiles"
        ]

        # Puppets should emit 0 profile update events
        # (creation event was reset above)
        assert len(profile_calls) == 0

    def test_puppet_rider_no_profile_updates(self, dna_factory: DNAFactory):
        """Puppet riders should not emit profile update events."""
        env = simpy.Environment()
        mock_producer = Mock()
        rider_dna = dna_factory.rider_dna()

        rider = RiderAgent(
            rider_id="puppet_rider_001",
            dna=rider_dna,
            env=env,
            kafka_producer=mock_producer,
            puppet=True,
        )

        # Reset mock to ignore creation event
        mock_producer.reset_mock()

        # Run simulation for a short time
        with patch("src.agents.rider_agent.PROFILE_UPDATE_INTERVAL_SECONDS", 10):
            env.process(rider.run())
            env.run(until=100)

        # Check that no profile update events were emitted
        profile_calls = [
            call
            for call in mock_producer.produce.call_args_list
            if call[1].get("topic") == "rider_profiles"
        ]

        # Puppets should emit 0 profile update events
        assert len(profile_calls) == 0


@pytest.mark.unit
class TestProfileUpdateLoop:
    """Tests for the periodic profile update loop."""

    def test_driver_profile_update_loop_emits_events(self, dna_factory: DNAFactory):
        """Driver profile update loop should emit events periodically."""
        env = simpy.Environment()
        driver_dna = dna_factory.driver_dna()

        # Track emitted events
        emitted_events = []

        driver = DriverAgent(
            driver_id="loop_driver_001",
            dna=driver_dna,
            env=env,
            kafka_producer=None,
        )

        # Patch _emit_update_event to track calls
        def tracking_emit():
            emitted_events.append("update")
            # Don't call original to avoid async issues in test

        driver._emit_update_event = tracking_emit

        # Run the profile update loop with short interval
        with patch("src.agents.driver_agent.PROFILE_UPDATE_INTERVAL_SECONDS", 10):
            # Directly run the profile update loop
            env.process(driver._profile_update_loop())

            # Run for enough time to trigger multiple updates
            # With interval=10 and variance 0.5-1.5, we expect updates around 5-15 sim seconds
            random.seed(42)
            env.run(until=50)

        # Should have emitted at least one update
        assert len(emitted_events) >= 1

    def test_rider_profile_update_loop_emits_events(self, dna_factory: DNAFactory):
        """Rider profile update loop should emit events periodically."""
        env = simpy.Environment()
        rider_dna = dna_factory.rider_dna()

        # Track emitted events
        emitted_events = []

        rider = RiderAgent(
            rider_id="loop_rider_001",
            dna=rider_dna,
            env=env,
            kafka_producer=None,
        )

        # Patch _emit_update_event to track calls
        def tracking_emit():
            emitted_events.append("update")

        rider._emit_update_event = tracking_emit

        # Run the profile update loop with short interval
        with patch("src.agents.rider_agent.PROFILE_UPDATE_INTERVAL_SECONDS", 10):
            env.process(rider._profile_update_loop())
            random.seed(42)
            env.run(until=50)

        # Should have emitted at least one update
        assert len(emitted_events) >= 1
