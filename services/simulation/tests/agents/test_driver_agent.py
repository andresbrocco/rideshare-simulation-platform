import json
from unittest.mock import Mock

import pytest
import simpy

from src.agents.dna import DriverDNA, ShiftPreference
from src.agents.driver_agent import DriverAgent
from tests.factories import DNAFactory


@pytest.fixture
def driver_dna(dna_factory: DNAFactory):
    return dna_factory.driver_dna()


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def driver_agent(simpy_env, driver_dna, mock_kafka_producer):
    agent = DriverAgent(
        driver_id="driver_001",
        dna=driver_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    mock_kafka_producer.reset_mock()
    return agent


@pytest.mark.unit
class TestDriverAgentInit:
    def test_driver_agent_init(self, simpy_env, driver_dna, mock_kafka_producer):
        agent = DriverAgent(
            driver_id="driver_001",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        assert agent.driver_id == "driver_001"
        assert agent.dna == driver_dna

    def test_driver_initial_state(self, driver_agent, driver_dna):
        assert driver_agent.status == "offline"
        # Location is now set from DNA home_location on creation
        assert driver_agent.location == driver_dna.home_location
        assert driver_agent.active_trip is None
        assert driver_agent.current_rating == 5.0
        assert driver_agent.rating_count == 0


@pytest.mark.unit
class TestDriverDNAImmutability:
    def test_driver_dna_immutability(self, driver_agent, driver_dna, dna_factory: DNAFactory):
        original_acceptance = driver_dna.acceptance_rate
        # Attempting to assign new DNA should not change it
        with pytest.raises(AttributeError):
            driver_agent.dna = dna_factory.driver_dna(
                acceptance_rate=0.5,
                shift_preference=ShiftPreference.NIGHT,
            )
        # Original DNA should be unchanged
        assert driver_agent.dna.acceptance_rate == original_acceptance


@pytest.mark.unit
class TestDriverStatusTransitions:
    def test_driver_status_transition_offline_to_online(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        assert driver_agent.status == "online"
        mock_kafka_producer.produce.assert_called()

    def test_driver_status_transition_online_to_en_route_pickup(
        self, driver_agent, mock_kafka_producer
    ):
        """Accept trip transitions directly to en_route_pickup."""
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        mock_kafka_producer.reset_mock()

        driver_agent.accept_trip("trip_001")
        assert driver_agent.status == "en_route_pickup"
        assert driver_agent.active_trip == "trip_001"
        mock_kafka_producer.produce.assert_called()

    def test_driver_status_transition_en_route_to_in_transit(
        self, driver_agent, mock_kafka_producer
    ):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        driver_agent.accept_trip("trip_001")
        driver_agent.start_pickup()
        mock_kafka_producer.reset_mock()

        driver_agent.start_trip()
        assert driver_agent.status == "en_route_destination"
        mock_kafka_producer.produce.assert_called()

    def test_driver_status_transition_to_online(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        driver_agent.accept_trip("trip_001")
        driver_agent.start_pickup()
        driver_agent.start_trip()
        mock_kafka_producer.reset_mock()

        driver_agent.complete_trip()
        assert driver_agent.status == "online"
        assert driver_agent.active_trip is None
        mock_kafka_producer.produce.assert_called()

    def test_driver_go_offline(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        mock_kafka_producer.reset_mock()

        driver_agent.go_offline()
        assert driver_agent.status == "offline"
        mock_kafka_producer.produce.assert_called()


@pytest.mark.unit
class TestDriverStateManagement:
    def test_driver_location_update(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        assert driver_agent.location == (-23.55, -46.63)
        # Location update should NOT emit event
        mock_kafka_producer.produce.assert_not_called()

    def test_driver_rating_update(self, driver_agent):
        assert driver_agent.current_rating == 5.0
        assert driver_agent.rating_count == 0

        driver_agent.update_rating(4)
        # (5.0 * 0 + 4) / 1 = 4.0
        assert driver_agent.current_rating == 4.0
        assert driver_agent.rating_count == 1

        driver_agent.update_rating(5)
        # (4.0 * 1 + 5) / 2 = 4.5
        assert driver_agent.current_rating == 4.5
        assert driver_agent.rating_count == 2


@pytest.mark.unit
class TestDriverEventEmission:
    def test_driver_status_event_emission(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()

        mock_kafka_producer.produce.assert_called_once()
        call_args = mock_kafka_producer.produce.call_args

        assert call_args.kwargs["topic"] == "driver_status"
        assert call_args.kwargs["key"] == "driver_001"

        # The value is now a DriverStatusEvent Pydantic model
        event = call_args.kwargs["value"]
        assert event.driver_id == "driver_001"
        assert event.previous_status == "offline"
        assert event.new_status == "online"
        assert event.trigger == "go_online"
        assert event.location == (-23.55, -46.63)


@pytest.mark.unit
class TestDriverSimpyProcess:
    def test_driver_agent_is_simpy_process(self, driver_agent, simpy_env):
        process = simpy_env.process(driver_agent.run())
        assert process is not None
        # Run the simulation briefly to ensure no errors
        simpy_env.run(until=1)


@pytest.mark.unit
class TestDriverIdleGPSSkip:
    """Tests for idle GPS deduplication (skip emit when location unchanged)."""

    def test_stationary_idle_driver_emits_no_repeat_gps_events(
        self, simpy_env, driver_dna, mock_kafka_producer
    ):
        """After the first ping, a stationary idle driver does not emit further GPS pings."""
        agent = DriverAgent(
            driver_id="driver_gps_idle_001",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()

        # Prime _last_emitted_location so the first interval is already "seen"
        agent._last_emitted_location = agent.location
        mock_kafka_producer.reset_mock()

        # Run the GPS ping loop for several idle intervals with location unchanged
        from src.agents.event_emitter import GPS_PING_INTERVAL_IDLE

        gps_process = simpy_env.process(agent._emit_gps_ping())
        simpy_env.run(until=GPS_PING_INTERVAL_IDLE * 3 + 1)
        gps_process.interrupt()

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]
        assert len(gps_calls) == 0, (
            f"Stationary idle driver emitted {len(gps_calls)} GPS pings after "
            "location was already known; expected 0."
        )

    def test_moving_driver_emits_gps_on_location_change(
        self, simpy_env, driver_dna, mock_kafka_producer
    ):
        """Driver emits GPS ping after each location update."""
        agent = DriverAgent(
            driver_id="driver_gps_moving_001",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()
        mock_kafka_producer.reset_mock()

        from src.agents.event_emitter import GPS_PING_INTERVAL_IDLE

        gps_process = simpy_env.process(agent._emit_gps_ping())

        # Change location between intervals to trigger emission
        simpy_env.run(until=GPS_PING_INTERVAL_IDLE)
        agent.update_location(-23.56, -46.64)
        simpy_env.run(until=GPS_PING_INTERVAL_IDLE * 2)
        agent.update_location(-23.57, -46.65)
        simpy_env.run(until=GPS_PING_INTERVAL_IDLE * 3 + 1)
        gps_process.interrupt()

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]
        assert len(gps_calls) >= 2, (
            f"Moving driver emitted only {len(gps_calls)} GPS pings; "
            "expected at least 2 after two location changes."
        )

    def test_last_emitted_location_resets_on_go_offline(self, driver_agent, mock_kafka_producer):
        """_last_emitted_location is cleared when driver goes offline."""
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        driver_agent._last_emitted_location = (-23.55, -46.63)

        driver_agent.go_offline()

        assert driver_agent._last_emitted_location is None
