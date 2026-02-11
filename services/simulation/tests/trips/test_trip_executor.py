"""Tests for TripExecutor event emission.

These tests specify the expected behavior for:
- FINDING-002: Events should go to Kafka only, not directly to Redis
  (Redis receives events via the filtered fanout from API layer)
"""

from unittest.mock import Mock, patch

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.geo.osrm_client import RouteResponse
from src.settings import SimulationSettings
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
        driver_id="driver_executor_001",
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
        rider_id="rider_executor_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )
    agent.update_location(-23.54, -46.62)
    return agent


@pytest.fixture
def sample_trip():
    """Sample trip for testing."""
    return Trip(
        trip_id="trip_executor_001",
        rider_id="rider_executor_001",
        driver_id="driver_executor_001",
        state=TripState.MATCHED,
        pickup_location=(-23.54, -46.62),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone_1",
        dropoff_zone_id="zone_2",
        surge_multiplier=1.0,
        fare=25.50,
    )


@pytest.fixture
def mock_osrm_client_for_executor():
    """OSRM client that returns simple routes."""
    client = Mock()

    def mock_get_route_sync(origin, destination):
        num_points = 11
        geometry = []
        for i in range(num_points):
            progress = i / (num_points - 1)
            lat = origin[0] + (destination[0] - origin[0]) * progress
            lon = origin[1] + (destination[1] - origin[1]) * progress
            geometry.append((lat, lon))

        return RouteResponse(
            distance_meters=2000.0,
            duration_seconds=300.0,  # 5 minutes
            geometry=geometry,
            osrm_code="Ok",
        )

    client.get_route_sync = Mock(side_effect=mock_get_route_sync)
    return client


@pytest.mark.unit
@pytest.mark.slow
class TestTripExecutorKafkaOnly:
    """Tests to verify TripExecutor emits to Kafka only, not Redis.

    FINDING-002 states that 5 locations still publish directly to Redis,
    causing duplicate messages. The fix is to have TripExecutor emit
    to Kafka only - Redis should receive events via the API layer's
    filtered fanout mechanism.
    """

    def test_trip_executor_emits_to_kafka_only(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Verify _emit_trip_event calls Kafka but NOT Redis.

        After the fix, TripExecutor should only emit trip events to Kafka.
        The Redis publisher parameter should be removed or ignored.
        """
        mock_redis_publisher = Mock()

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,  # Should NOT be used
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Verify Kafka was used for trip events
        kafka_trip_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "trips"
        ]
        assert len(kafka_trip_calls) > 0, "Trip events should be sent to Kafka"

        # Verify Redis was NOT used for trip events
        # After the fix, redis_publisher.publish and publish_sync should not be called
        # for trip-updates channel
        redis_publish_calls = mock_redis_publisher.publish.call_args_list
        redis_publish_sync_calls = mock_redis_publisher.publish_sync.call_args_list

        trip_update_redis_calls = [
            call
            for call in redis_publish_calls
            if "trip-updates" in str(call) or "trip" in str(call).lower()
        ]
        trip_update_redis_sync_calls = [
            call
            for call in redis_publish_sync_calls
            if "trip-updates" in str(call) or "trip" in str(call).lower()
        ]

        assert len(trip_update_redis_calls) == 0, (
            "Trip events should NOT be published directly to Redis. "
            "They should flow through Kafka -> API layer -> Redis fanout."
        )
        assert len(trip_update_redis_sync_calls) == 0, (
            "Trip events should NOT be published directly to Redis (sync). "
            "They should flow through Kafka -> API layer -> Redis fanout."
        )

    def test_gps_ping_emits_to_kafka_only(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Verify _emit_gps_ping calls Kafka but NOT Redis.

        GPS pings should only go to Kafka. The Redis fanout for real-time
        visualization should be handled by the API layer, not TripExecutor.
        """
        mock_redis_publisher = Mock()

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            redis_publisher=mock_redis_publisher,  # Should NOT be used
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Verify Kafka was used for GPS pings
        kafka_gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]
        assert len(kafka_gps_calls) > 0, "GPS pings should be sent to Kafka"

        # Verify Redis was NOT used for GPS pings
        # After the fix, redis_publisher.publish_sync should not be called
        # for driver-updates or rider-updates channels
        redis_sync_calls = mock_redis_publisher.publish_sync.call_args_list

        gps_redis_calls = [
            call
            for call in redis_sync_calls
            if "driver-updates" in str(call) or "rider-updates" in str(call)
        ]

        assert len(gps_redis_calls) == 0, (
            "GPS pings should NOT be published directly to Redis. "
            "They should flow through Kafka -> API layer -> Redis fanout."
        )

    def test_trip_executor_works_without_redis_publisher(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Verify TripExecutor works correctly with redis_publisher=None.

        After the consolidation, redis_publisher should be optional and
        the executor should work correctly without it.
        """
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            redis_publisher=None,  # No Redis publisher
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Trip should complete successfully
        assert sample_trip.state == TripState.COMPLETED

        # Kafka should have received events
        kafka_calls = mock_kafka_producer.produce.call_args_list
        assert len(kafka_calls) > 0, "Kafka should receive events"
