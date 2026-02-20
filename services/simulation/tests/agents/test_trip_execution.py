import random
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import simpy

from src.agents.dna import DriverDNA, RiderDNA
from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.geo.osrm_client import RouteResponse
from src.trip import Trip, TripState
from src.trips.trip_executor import TripExecutor
from tests.factories import DNAFactory


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def driver_dna(dna_factory: DNAFactory):
    return dna_factory.driver_dna(acceptance_rate=0.9)


@pytest.fixture
def rider_dna(dna_factory: DNAFactory):
    return dna_factory.rider_dna()


@pytest.fixture
def driver_agent(simpy_env, driver_dna, mock_kafka_producer):
    agent = DriverAgent(
        driver_id="driver_001",
        dna=driver_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.55, -46.63)
    agent.go_online()
    return agent


@pytest.fixture
def rider_agent(simpy_env, rider_dna, mock_kafka_producer):
    agent = RiderAgent(
        rider_id="rider_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.54, -46.62)
    return agent


@pytest.fixture
def trip():
    return Trip(
        trip_id="trip_001",
        rider_id="rider_001",
        driver_id="driver_001",
        state=TripState.DRIVER_ASSIGNED,
        pickup_location=(-23.54, -46.62),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone_1",
        dropoff_zone_id="zone_2",
        surge_multiplier=1.2,
        fare=25.50,
    )


@pytest.fixture
def mock_osrm_client():
    client = Mock()

    async def mock_get_route(origin, destination):
        return RouteResponse(
            distance_meters=5000.0,
            duration_seconds=600.0,
            geometry=[
                origin,
                ((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2),
                destination,
            ],
            osrm_code="Ok",
        )

    def mock_get_route_sync(origin, destination):
        """Synchronous version for use in SimPy thread."""
        return RouteResponse(
            distance_meters=5000.0,
            duration_seconds=600.0,
            geometry=[
                origin,
                ((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2),
                destination,
            ],
            osrm_code="Ok",
        )

    client.get_route = AsyncMock(side_effect=mock_get_route)
    client.get_route_sync = Mock(side_effect=mock_get_route_sync)
    return client


@pytest.fixture
def trip_executor(
    simpy_env, driver_agent, rider_agent, trip, mock_osrm_client, mock_kafka_producer
):
    return TripExecutor(
        env=simpy_env,
        driver=driver_agent,
        rider=rider_agent,
        trip=trip,
        osrm_client=mock_osrm_client,
        kafka_producer=mock_kafka_producer,
    )


@pytest.mark.unit
@pytest.mark.slow
class TestTripFullFlow:
    def test_trip_full_flow_success(
        self, simpy_env, trip_executor, driver_agent, rider_agent, trip
    ):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        assert trip.state == TripState.COMPLETED
        assert driver_agent.status == "available"
        assert rider_agent.status == "idle"
        assert driver_agent.active_trip is None
        assert rider_agent.active_trip is None


@pytest.mark.unit
@pytest.mark.slow
class TestTripEvents:
    def test_trip_driver_en_route_event(self, simpy_env, trip_executor, mock_kafka_producer):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        event_types = [
            (evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", None))
            for evt in events
        ]

        assert "trip.en_route_pickup" in event_types

    def test_trip_driver_arrived_event(self, simpy_env, trip_executor, mock_kafka_producer):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        event_types = [
            (evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", None))
            for evt in events
        ]

        assert "trip.at_pickup" in event_types

    def test_trip_started_event(self, simpy_env, trip_executor, mock_kafka_producer):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        event_types = [
            (evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", None))
            for evt in events
        ]

        assert "trip.in_transit" in event_types

    def test_trip_completed_event(self, simpy_env, trip_executor, mock_kafka_producer):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        event_types = [
            (evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", None))
            for evt in events
        ]

        assert "trip.completed" in event_types

    def test_trip_payment_event_on_completion(self, simpy_env, trip_executor, mock_kafka_producer):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        payment_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "payments"
        ]

        assert len(payment_calls) > 0


@pytest.mark.unit
@pytest.mark.slow
class TestTripCancellation:
    def test_trip_driver_wait_timeout(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            wait_timeout=10,
            rider_boards=False,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip.state == TripState.CANCELLED
        assert trip.cancelled_by == "driver"
        assert trip.cancellation_reason == "no_show"

    def test_trip_driver_cancellation_no_show(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            wait_timeout=10,
            rider_boards=False,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        events = [
            call[1]["value"]
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]

        cancelled_events = [
            evt
            for evt in events
            if (isinstance(evt, dict) and evt.get("event_type") == "trip.cancelled")
            or (hasattr(evt, "event_type") and evt.event_type == "trip.cancelled")
        ]

        assert len(cancelled_events) > 0

    def test_trip_rider_cancellation_during_trip(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        trip,
        mock_osrm_client,
        mock_kafka_producer,
    ):
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip,
            osrm_client=mock_osrm_client,
            kafka_producer=mock_kafka_producer,
            rider_cancels_mid_trip=True,
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert trip.state == TripState.CANCELLED
        assert trip.cancelled_by == "rider"


@pytest.mark.unit
@pytest.mark.slow
class TestGPSUpdates:
    def test_trip_gps_updates_during_transit(
        self, simpy_env, trip_executor, driver_agent, mock_kafka_producer
    ):
        # Start the driver's GPS ping loop alongside the trip executor
        # GPS emission is now the agent's responsibility, not TripExecutor's
        simpy_env.process(driver_agent._emit_gps_ping())
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]

        assert len(gps_calls) > 0

    def test_trip_driver_location_updates(self, simpy_env, trip_executor, driver_agent):
        initial_location = driver_agent.location

        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        assert driver_agent.location != initial_location

    def test_trip_rider_location_updates(self, simpy_env, trip_executor, rider_agent):
        initial_location = rider_agent.location

        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        assert rider_agent.location != initial_location


@pytest.mark.unit
@pytest.mark.slow
class TestTripTiming:
    def test_trip_timing_pickup_drive(self, simpy_env, trip_executor, mock_osrm_client):
        start_time = simpy_env.now

        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        elapsed = simpy_env.now - start_time
        assert elapsed > 0
        # Uses get_route_sync for synchronous OSRM calls in SimPy thread
        assert mock_osrm_client.get_route_sync.call_count >= 2

    def test_trip_timing_trip_drive(self, simpy_env, trip_executor):
        start_time = simpy_env.now

        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        elapsed = simpy_env.now - start_time
        assert elapsed > 600


@pytest.mark.unit
@pytest.mark.slow
class TestAgentStatusTransitions:
    def test_trip_driver_status_transitions(self, simpy_env, trip_executor, driver_agent):
        assert driver_agent.status == "available"

        simpy_env.process(trip_executor.execute())
        simpy_env.run(until=simpy_env.now + 1)

        assert driver_agent.status in [
            "en_route_pickup",
            "on_trip",
            "available",
        ]

    def test_trip_rider_status_transitions(self, simpy_env, trip_executor, rider_agent):
        process = simpy_env.process(trip_executor.execute())
        simpy_env.run(process)

        assert rider_agent.status == "idle"


@pytest.mark.unit
@pytest.mark.slow
class TestDriverOfferResponse:
    def test_driver_receive_offer_accepts(self, simpy_env, dna_factory, mock_kafka_producer):
        accepting_dna = dna_factory.driver_dna(acceptance_rate=1.0)
        driver = DriverAgent(
            driver_id="driver_002",
            dna=accepting_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        offer = {
            "trip_id": "trip_002",
            "surge_multiplier": 1.0,
            "rider_rating": 5.0,
        }

        random.seed(42)
        accepts = driver.receive_offer(offer)

        assert accepts is True

    def test_driver_receive_offer_rejects(self, simpy_env, dna_factory, mock_kafka_producer):
        rejecting_dna = dna_factory.driver_dna(acceptance_rate=0.0)
        driver = DriverAgent(
            driver_id="driver_003",
            dna=rejecting_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        offer = {
            "trip_id": "trip_003",
            "surge_multiplier": 1.0,
            "rider_rating": 5.0,
        }

        random.seed(42)
        accepts = driver.receive_offer(offer)

        assert accepts is False


@pytest.mark.unit
@pytest.mark.slow
class TestNotificationHandlers:
    def test_rider_on_match_found(self, simpy_env, rider_dna, mock_kafka_producer):
        rider = RiderAgent(
            rider_id="rider_002",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip_004",
            rider_id="rider_002",
            driver_id="driver_004",
            state=TripState.DRIVER_ASSIGNED,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        rider.on_match_found(trip, "driver_004")
        assert rider.status == "requesting"

    def test_rider_on_no_drivers_available(self, simpy_env, rider_dna, mock_kafka_producer):
        rider = RiderAgent(
            rider_id="rider_003",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        rider.on_no_drivers_available("trip_005")

    def test_driver_on_trip_cancelled_by_rider(self, simpy_env, driver_dna, mock_kafka_producer):
        driver = DriverAgent(
            driver_id="driver_005",
            dna=driver_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        driver.go_online()
        driver.accept_trip("trip_006")

        trip = Trip(
            trip_id="trip_006",
            rider_id="rider_004",
            driver_id="driver_005",
            state=TripState.CANCELLED,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
            cancelled_by="rider",
        )

        driver.on_trip_cancelled(trip)
        assert driver.status == "available"

    def test_rider_on_trip_cancelled_by_driver(self, simpy_env, rider_dna, mock_kafka_producer):
        rider = RiderAgent(
            rider_id="rider_005",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        rider.request_trip("trip_007")

        trip = Trip(
            trip_id="trip_007",
            rider_id="rider_005",
            driver_id="driver_006",
            state=TripState.CANCELLED,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
            cancelled_by="driver",
        )

        rider.on_trip_cancelled(trip)
        assert rider.status == "idle"

    def test_rider_on_driver_en_route(self, simpy_env, rider_dna, mock_kafka_producer):
        rider = RiderAgent(
            rider_id="rider_006",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip_008",
            rider_id="rider_006",
            driver_id="driver_007",
            state=TripState.EN_ROUTE_PICKUP,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        rider.on_driver_en_route(trip)

    def test_rider_on_driver_arrived(self, simpy_env, rider_dna, mock_kafka_producer):
        rider = RiderAgent(
            rider_id="rider_007",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )

        trip = Trip(
            trip_id="trip_009",
            rider_id="rider_007",
            driver_id="driver_008",
            state=TripState.AT_PICKUP,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        rider.on_driver_arrived(trip)
