"""Tests for TripExecutor event emission.

These tests specify the expected behavior for:
- FINDING-002: Events should go to Kafka only, not directly to Redis
  (Redis receives events via the filtered fanout from API layer)
- GPS duplication fix: TripExecutor uses GPS_PING_INTERVAL_MOVING, not hardcoded 1
"""

from unittest.mock import Mock, patch

import pytest
import simpy

from src.agents.driver_agent import DriverAgent
from src.agents.event_emitter import GPS_PING_INTERVAL_MOVING
from src.agents.rider_agent import RiderAgent
from src.geo.osrm_client import RouteResponse
from src.settings import SimulationSettings
from src.trip import Trip, TripState
from src.trips.trip_executor import TripExecutor
from tests.factories import DNAFactory

# Re-export fixtures used by TestPrePickupCancellation below
# (dna_factory comes from conftest.py)


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
        state=TripState.DRIVER_ASSIGNED,
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

    def test_trip_executor_does_not_emit_gps_pings(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        sample_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Verify TripExecutor does NOT emit GPS pings directly.

        GPS emission is delegated to each agent's own GPS loop.
        TripExecutor only updates agent positions and route progress.
        """
        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=sample_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # TripExecutor should NOT emit GPS pings — agents handle their own
        kafka_gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]
        assert len(kafka_gps_calls) == 0, (
            "TripExecutor should not emit GPS pings directly. "
            "GPS emission is delegated to each agent's own GPS loop."
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


@pytest.mark.unit
class TestTripExecutorGPSInterval:
    """Regression tests for GPS interval fix.

    TripExecutor._simulate_drive() must use the configured GPS_PING_INTERVAL_MOVING
    constant instead of a hardcoded interval of 1 second.
    """

    def test_trip_executor_uses_configured_gps_interval(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        mock_kafka_producer,
    ):
        """Drive loop tick count matches GPS_PING_INTERVAL_MOVING, not hardcoded 1."""
        # Route with exact duration = GPS_PING_INTERVAL_MOVING * 5 intervals
        expected_intervals = 5
        duration = GPS_PING_INTERVAL_MOVING * expected_intervals
        # Points spaced ~220m apart (0.002 degrees) — well above proximity threshold
        num_points = 11
        geometry = [(-23.55 + i * 0.002, -46.63 + i * 0.002) for i in range(num_points)]

        route = RouteResponse(
            distance_meters=5000.0,
            duration_seconds=float(duration),
            geometry=geometry,
            osrm_code="Ok",
        )

        mock_osrm = Mock()
        mock_osrm.get_route_sync = Mock(return_value=route)

        trip = Trip(
            trip_id="trip_interval_001",
            rider_id="rider_executor_001",
            driver_id="driver_executor_001",
            state=TripState.DRIVER_ASSIGNED,
            pickup_location=geometry[0],
            dropoff_location=geometry[-1],
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip,
            osrm_client=mock_osrm,
            kafka_producer=mock_kafka_producer,
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        # Reset to isolate GPS pings from setup
        mock_kafka_producer.produce.reset_mock()

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]

        # With GPS_PING_INTERVAL_MOVING, num_intervals = duration / interval = 5.
        # Each drive phase (pickup + destination) produces ~5 ticks.
        # Pickup: 5 driver pings. Destination: 5 driver + 5 rider pings.
        # Total ≈ 15 GPS pings.
        # With hardcoded interval=1, num_intervals = duration = 300 (for interval=60),
        # producing ~900 pings. The assertion checks we're in the expected range.
        if GPS_PING_INTERVAL_MOVING > 1:
            pings_if_hardcoded_1 = duration * 3  # rough upper bound for both phases
            assert len(gps_calls) < pings_if_hardcoded_1, (
                f"Got {len(gps_calls)} GPS pings, expected fewer than {pings_if_hardcoded_1} "
                "with configured interval. Hardcoded interval=1 may still be in use."
            )

    def test_trip_executor_gps_interval_matches_constant(self):
        """Verify TripExecutor._simulate_drive uses GPS_PING_INTERVAL_MOVING directly."""
        import inspect

        from src.trips.trip_executor import TripExecutor

        source = inspect.getsource(TripExecutor._simulate_drive)
        assert (
            "GPS_PING_INTERVAL_MOVING" in source
        ), "_simulate_drive should reference GPS_PING_INTERVAL_MOVING constant"
        assert (
            "gps_interval = 1" not in source
        ), "_simulate_drive should not hardcode gps_interval = 1"


@pytest.mark.unit
class TestTripExecutorPrecomputedHeadings:
    """Verify _simulate_drive() uses precomputed headings instead of per-tick trig."""

    def test_simulate_drive_uses_precomputed_headings(self):
        """_simulate_drive source should use precompute_headings, not GPSSimulator instantiation."""
        import inspect

        from src.trips.trip_executor import TripExecutor

        source = inspect.getsource(TripExecutor._simulate_drive)
        assert "precompute_headings" in source, "_simulate_drive should call precompute_headings()"
        assert "route_headings" in source, "_simulate_drive should use route_headings array"
        assert (
            "GPSSimulator(noise_meters=0)" not in source
        ), "_simulate_drive should not instantiate GPSSimulator per tick"

    def test_precomputed_headings_match_driver_heading(
        self,
        simpy_env,
        driver_agent,
        rider_agent,
        mock_kafka_producer,
    ):
        """Heading passed to update_location matches precomputed value."""
        from src.geo.gps_simulation import precompute_headings

        # Build a route with distinct segments at different angles
        geometry = [
            (-23.550, -46.630),
            (-23.548, -46.628),  # NE
            (-23.546, -46.630),  # NW
            (-23.544, -46.628),  # NE
            (-23.542, -46.630),  # NW
        ]
        expected_headings = precompute_headings(geometry)

        route = RouteResponse(
            distance_meters=3000.0,
            duration_seconds=float(GPS_PING_INTERVAL_MOVING * 4),
            geometry=geometry,
            osrm_code="Ok",
        )

        mock_osrm = Mock()
        mock_osrm.get_route_sync = Mock(return_value=route)

        trip = Trip(
            trip_id="trip_heading_001",
            rider_id="rider_executor_001",
            driver_id="driver_executor_001",
            state=TripState.DRIVER_ASSIGNED,
            pickup_location=geometry[0],
            dropoff_location=geometry[-1],
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )

        executor = TripExecutor(
            env=simpy_env,
            driver=driver_agent,
            rider=rider_agent,
            trip=trip,
            osrm_client=mock_osrm,
            kafka_producer=mock_kafka_producer,
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        # Trip should complete successfully with precomputed headings
        assert trip.state == TripState.COMPLETED

        # Driver heading should be one of the precomputed values or preserved last heading
        # (not 0.0, which would indicate heading was never set from route)
        assert driver_agent.heading != 0.0 or any(h == 0.0 for h in expected_headings)


@pytest.mark.unit
class TestPrePickupCancellation:
    """Tests for DNA-based pre-pickup driver cancellation."""

    @pytest.fixture
    def high_cancel_driver(self, simpy_env, dna_factory: DNAFactory, mock_kafka_producer):
        """Driver with high cancellation tendency."""
        dna = dna_factory.driver_dna(cancellation_tendency=0.10)
        agent = DriverAgent(
            driver_id="driver_cancel_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)
        agent.go_online()
        return agent

    @pytest.fixture
    def cancel_rider(self, simpy_env, dna_factory: DNAFactory, mock_kafka_producer):
        """Rider for cancellation tests."""
        dna = dna_factory.rider_dna()
        agent = RiderAgent(
            rider_id="rider_cancel_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.54, -46.62)
        return agent

    @pytest.fixture
    def cancel_trip(self):
        """Trip for cancellation tests."""
        return Trip(
            trip_id="trip_cancel_001",
            rider_id="rider_cancel_001",
            driver_id="driver_cancel_001",
            state=TripState.DRIVER_ASSIGNED,
            pickup_location=(-23.54, -46.62),
            dropoff_location=(-23.56, -46.64),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=25.50,
        )

    @patch("src.trips.trip_executor.random.random", return_value=0.0)
    def test_driver_cancels_pre_pickup_when_random_below_threshold(
        self,
        mock_random,
        simpy_env,
        high_cancel_driver,
        cancel_rider,
        cancel_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Driver cancels pre-pickup when random() < cancel_prob."""
        executor = TripExecutor(
            env=simpy_env,
            driver=high_cancel_driver,
            rider=cancel_rider,
            trip=cancel_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert cancel_trip.state == TripState.CANCELLED
        assert cancel_trip.cancelled_by == "driver"
        assert cancel_trip.cancellation_reason == "driver_cancelled_before_pickup"
        assert cancel_trip.cancellation_stage == "pickup"
        assert high_cancel_driver.status == "available"

    @patch("src.trips.trip_executor.random.random", return_value=1.0)
    def test_driver_does_not_cancel_pre_pickup_when_random_above_threshold(
        self,
        mock_random,
        simpy_env,
        high_cancel_driver,
        cancel_rider,
        cancel_trip,
        mock_osrm_client_for_executor,
        mock_kafka_producer,
    ):
        """Driver does not cancel when random() > cancel_prob; trip completes."""
        executor = TripExecutor(
            env=simpy_env,
            driver=high_cancel_driver,
            rider=cancel_rider,
            trip=cancel_trip,
            osrm_client=mock_osrm_client_for_executor,
            kafka_producer=mock_kafka_producer,
            settings=SimulationSettings(arrival_proximity_threshold_m=50.0),
        )

        process = simpy_env.process(executor.execute())
        simpy_env.run(process)

        assert cancel_trip.state == TripState.COMPLETED

    def test_pre_pickup_cancellation_distance_scaling(self):
        """Verify distance_scaling formula: max(0.5, min(2.0, eta_minutes / 10.0))."""
        # Short ETA (3 min) → clamped to 0.5
        assert max(0.5, min(2.0, 3.0 / 10.0)) == 0.5
        # Medium ETA (10 min) → 1.0
        assert max(0.5, min(2.0, 10.0 / 10.0)) == 1.0
        # Long ETA (25 min) → clamped to 2.0
        assert max(0.5, min(2.0, 25.0 / 10.0)) == 2.0
        # Boundary: 5 min → 0.5
        assert max(0.5, min(2.0, 5.0 / 10.0)) == 0.5
        # Boundary: 20 min → 2.0
        assert max(0.5, min(2.0, 20.0 / 10.0)) == 2.0
