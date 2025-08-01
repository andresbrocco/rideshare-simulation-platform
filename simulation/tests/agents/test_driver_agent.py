import json
from unittest.mock import Mock

import pytest
import simpy

from agents.dna import DriverDNA, ShiftPreference
from agents.driver_agent import DriverAgent


@pytest.fixture
def driver_dna():
    return DriverDNA(
        acceptance_rate=0.85,
        cancellation_tendency=0.05,
        service_quality=0.9,
        response_time=5.0,
        min_rider_rating=3.5,
        home_location=(-23.55, -46.63),
        preferred_zones=["zone_1", "zone_2"],
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="João",
        last_name="Silva",
        email="joao@example.com",
        phone="+5511999999999",
    )


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


@pytest.fixture
def driver_agent(simpy_env, driver_dna, mock_kafka_producer):
    return DriverAgent(
        driver_id="driver_001",
        dna=driver_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )


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

    def test_driver_initial_state(self, driver_agent):
        assert driver_agent.status == "offline"
        assert driver_agent.location is None
        assert driver_agent.active_trip is None
        assert driver_agent.current_rating == 5.0
        assert driver_agent.rating_count == 0


class TestDriverDNAImmutability:
    def test_driver_dna_immutability(self, driver_agent, driver_dna):
        original_acceptance = driver_dna.acceptance_rate
        # Attempting to assign new DNA should not change it
        with pytest.raises(AttributeError):
            driver_agent.dna = DriverDNA(
                acceptance_rate=0.5,
                cancellation_tendency=0.1,
                service_quality=0.5,
                response_time=10.0,
                min_rider_rating=4.0,
                home_location=(-23.55, -46.63),
                preferred_zones=["zone_3"],
                shift_preference=ShiftPreference.NIGHT,
                avg_hours_per_day=4,
                avg_days_per_week=3,
                vehicle_make="Honda",
                vehicle_model="Civic",
                vehicle_year=2019,
                license_plate="XYZ-9999",
                first_name="Maria",
                last_name="Santos",
                email="maria@example.com",
                phone="+5511888888888",
            )
        # Original DNA should be unchanged
        assert driver_agent.dna.acceptance_rate == original_acceptance


class TestDriverStatusTransitions:
    def test_driver_status_transition_offline_to_online(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        assert driver_agent.status == "online"
        mock_kafka_producer.produce.assert_called()

    def test_driver_status_transition_online_to_busy(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        mock_kafka_producer.reset_mock()

        driver_agent.accept_trip("trip_001")
        assert driver_agent.status == "busy"
        assert driver_agent.active_trip == "trip_001"
        mock_kafka_producer.produce.assert_called()

    def test_driver_status_transition_busy_to_en_route(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()
        driver_agent.accept_trip("trip_001")
        mock_kafka_producer.reset_mock()

        driver_agent.start_pickup()
        assert driver_agent.status == "en_route_pickup"
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


class TestDriverEventEmission:
    def test_driver_status_event_emission(self, driver_agent, mock_kafka_producer):
        driver_agent.update_location(-23.55, -46.63)
        driver_agent.go_online()

        mock_kafka_producer.produce.assert_called_once()
        call_args = mock_kafka_producer.produce.call_args

        assert call_args.kwargs["topic"] == "driver-status"
        assert call_args.kwargs["key"] == "driver_001"

        # Parse the event payload
        event_data = json.loads(call_args.kwargs["value"])
        assert event_data["driver_id"] == "driver_001"
        assert event_data["previous_status"] == "offline"
        assert event_data["new_status"] == "online"
        assert event_data["trigger"] == "go_online"
        assert event_data["location"] == [-23.55, -46.63]


class TestDriverSimpyProcess:
    def test_driver_agent_is_simpy_process(self, driver_agent, simpy_env):
        process = simpy_env.process(driver_agent.run())
        assert process is not None
        # Run the simulation briefly to ensure no errors
        simpy_env.run(until=1)
