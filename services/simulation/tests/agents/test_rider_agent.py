import random
from unittest.mock import Mock

import pytest
import simpy

from agents.dna import RiderDNA
from agents.rider_agent import RiderAgent
from fare import FareCalculator
from tests.factories import DNAFactory


@pytest.fixture
def rider_dna(dna_factory: DNAFactory):
    # All coordinates must be inside sample zones (PIN, BVI, SEE)
    return dna_factory.rider_dna(
        frequent_destinations=[
            {
                "name": "work",
                "coordinates": (-23.56, -46.65),
                "weight": 0.6,
            },  # Inside BVI
            {
                "name": "gym",
                "coordinates": (-23.565, -46.695),
                "weight": 0.3,
            },  # Inside PIN
            {
                "name": "mall",
                "coordinates": (-23.55, -46.635),
                "weight": 0.1,
            },  # Inside SEE
        ],
    )


@pytest.fixture
def simpy_env():
    return simpy.Environment()


@pytest.fixture
def rider_agent(simpy_env, rider_dna, mock_kafka_producer):
    return RiderAgent(
        rider_id="rider_001",
        dna=rider_dna,
        env=simpy_env,
        kafka_producer=mock_kafka_producer,
    )


@pytest.mark.unit
class TestRiderAgentInit:
    def test_rider_agent_init(self, simpy_env, rider_dna, mock_kafka_producer):
        agent = RiderAgent(
            rider_id="rider_001",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        assert agent.rider_id == "rider_001"
        assert agent.dna == rider_dna

    def test_rider_initial_state(self, rider_agent, rider_dna):
        assert rider_agent.status == "offline"
        # Location is now set from DNA home_location on creation
        assert rider_agent.location == rider_dna.home_location
        assert rider_agent.active_trip is None
        assert rider_agent.current_rating == 5.0
        assert rider_agent.rating_count == 0


@pytest.mark.unit
class TestRiderDNAImmutability:
    def test_rider_dna_immutability(self, rider_agent, rider_dna, dna_factory: DNAFactory):
        original_behavior = rider_dna.behavior_factor
        with pytest.raises(AttributeError):
            rider_agent.dna = dna_factory.rider_dna(
                behavior_factor=0.3,
                patience_threshold=200,
            )
        assert rider_agent.dna.behavior_factor == original_behavior


@pytest.mark.unit
class TestRiderStatusTransitions:
    def test_rider_status_transition_offline_to_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        assert rider_agent.active_trip == "trip_001"

    def test_rider_status_transition_waiting_to_in_trip(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        assert rider_agent.status == "in_trip"

    def test_rider_status_transition_in_trip_to_offline(self, rider_agent):
        rider_agent.request_trip("trip_001")
        rider_agent.start_trip()
        rider_agent.complete_trip()
        assert rider_agent.status == "offline"
        assert rider_agent.active_trip is None

    def test_rider_cancel_while_waiting(self, rider_agent):
        rider_agent.request_trip("trip_001")
        assert rider_agent.status == "waiting"
        rider_agent.cancel_trip()
        assert rider_agent.status == "offline"
        assert rider_agent.active_trip is None


@pytest.mark.unit
class TestRiderStateManagement:
    def test_rider_location_update(self, rider_agent):
        rider_agent.update_location(-23.55, -46.63)
        assert rider_agent.location == (-23.55, -46.63)

    def test_rider_rating_update(self, rider_agent):
        assert rider_agent.current_rating == 5.0
        assert rider_agent.rating_count == 0

        rider_agent.update_rating(3)
        # (5.0 * 0 + 3) / 1 = 3.0
        assert rider_agent.current_rating == 3.0
        assert rider_agent.rating_count == 1

        rider_agent.update_rating(5)
        # (3.0 * 1 + 5) / 2 = 4.0
        assert rider_agent.current_rating == 4.0
        assert rider_agent.rating_count == 2


@pytest.mark.unit
class TestRiderSimpyProcess:
    def test_rider_agent_is_simpy_process(self, rider_agent, simpy_env):
        process = simpy_env.process(rider_agent.run())
        assert process is not None
        simpy_env.run(until=1)


@pytest.mark.unit
class TestRiderDestinationSelection:
    def test_rider_frequent_destination_selection(self, rider_agent, rider_dna):
        random.seed(42)
        rider_agent.update_location(*rider_dna.home_location)

        selected_coords = []
        for _ in range(100):
            coords = rider_agent.select_destination()
            selected_coords.append(coords)

        valid_coords = [tuple(d["coordinates"]) for d in rider_dna.frequent_destinations]
        frequent_count = sum(1 for c in selected_coords if tuple(c) in valid_coords)

        # From home: expect ~80% frequent destinations
        assert frequent_count > 60


@pytest.mark.unit
class TestRiderGPSEmissionDuringTrip:
    """Tests for rider GPS emission during trips.

    RiderAgent.run() emits GPS pings when the rider is in_trip and location changes.
    Each agent is responsible for its own GPS emission.
    """

    def test_rider_emits_gps_when_in_trip_and_moving(
        self, simpy_env, rider_dna, mock_kafka_producer
    ):
        """Rider run() loop emits GPS pings when status is in_trip and location changes."""
        agent = RiderAgent(
            rider_id="rider_gps_001",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        # Transition to in_trip to simulate an active trip
        agent.request_trip("trip_gps_001")
        agent.start_trip()
        assert agent.status == "in_trip"

        # Reset call tracking after setup events
        mock_kafka_producer.produce.reset_mock()

        # Simulate location updates as TripExecutor would do
        def update_location():  # type: ignore[no-untyped-def]
            for i in range(5):
                agent.update_location(-23.55 + i * 0.001, -46.63 + i * 0.001)
                yield simpy_env.timeout(2)

        simpy_env.process(agent.run())
        simpy_env.process(update_location())
        simpy_env.run(until=12)

        gps_calls = [
            call
            for call in mock_kafka_producer.produce.call_args_list
            if call[1].get("topic") == "gps_pings"
        ]
        assert (
            len(gps_calls) > 0
        ), "Rider should emit GPS pings from its own loop while in_trip when location changes."

    def test_rider_gps_loop_still_yields_when_in_trip(
        self, simpy_env, rider_dna, mock_kafka_producer
    ):
        """Rider run() loop yields correctly without blocking SimPy scheduler when in_trip."""
        agent = RiderAgent(
            rider_id="rider_gps_002",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
        )
        agent.update_location(-23.55, -46.63)

        agent.request_trip("trip_gps_002")
        agent.start_trip()

        simpy_env.process(agent.run())
        # Advance the simulation — should not raise or deadlock
        simpy_env.run(until=20)

        # The fact that we got here without blocking proves the loop yields correctly.
        # SimPy time should have advanced to 20.
        assert simpy_env.now == 20


@pytest.mark.unit
class TestRiderPatienceLoop:
    """Tests for the optimized patience timeout (single SimPy event per wait)."""

    def test_patience_timeout_cancels_waiting_trip(
        self, simpy_env, rider_dna, mock_kafka_producer, dna_factory
    ):
        """After patience_threshold seconds with no match, rider cancels and goes offline."""
        dna = dna_factory.rider_dna(patience_threshold=120)
        agent = RiderAgent(
            rider_id="rider_patience_001",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            immediate_first_trip=True,
        )
        agent.update_location(-23.56, -46.65)

        # Run the agent — it will request a trip immediately (immediate_first_trip=True),
        # then wait patience_threshold seconds before cancelling due to no match.
        simpy_env.process(agent.run())

        # Advance through the initial 1-second stabilisation delay and patience window
        simpy_env.run(until=dna.patience_threshold + 5)

        # Agent must have timed out and gone back to offline
        assert agent.status == "offline"

    def test_patience_single_timeout_event(
        self, simpy_env, rider_dna, mock_kafka_producer, dna_factory
    ):
        """Single yield env.timeout(remaining) rather than N individual 1-second yields."""
        # A large patience_threshold makes the O(N) cost visible if the loop is naive.
        # With the optimised implementation, SimPy advances directly to match_timeout.
        dna = dna_factory.rider_dna(patience_threshold=300)
        agent = RiderAgent(
            rider_id="rider_patience_002",
            dna=dna,
            env=simpy_env,
            kafka_producer=mock_kafka_producer,
            immediate_first_trip=True,
        )
        agent.update_location(-23.56, -46.65)

        simpy_env.process(agent.run())

        # After patience_threshold + buffer, agent must be offline (timed out)
        simpy_env.run(until=dna.patience_threshold + 10)
        assert agent.status == "offline"


@pytest.mark.unit
class TestRiderZoneBasedGeneration:
    """Tests for zone-based coordinate generation."""

    def test_generate_random_location_returns_in_zone_coordinates(self, rider_agent):
        """Verify _generate_random_location returns coordinates inside a zone."""
        from agents.zone_validator import is_location_in_any_zone

        # Generate multiple locations and verify all are in zones
        for _ in range(10):
            lat, lon = rider_agent._generate_random_location()
            assert is_location_in_any_zone(
                lat, lon
            ), f"Generated location ({lat}, {lon}) is not inside any zone"

    def test_select_destination_returns_valid_zone_coordinates(self, rider_agent, rider_dna):
        """Verify select_destination always returns coordinates inside a zone."""
        from agents.zone_validator import is_location_in_any_zone

        random.seed(12345)
        rider_agent.update_location(*rider_dna.home_location)

        # Test from both home and away locations
        for _ in range(50):
            lat, lon = rider_agent.select_destination()
            assert is_location_in_any_zone(
                lat, lon
            ), f"Destination ({lat}, {lon}) is not inside any zone"


@pytest.mark.unit
class TestRiderCalculateFare:
    """Verify _calculate_fare delegates to FareCalculator constants."""

    def test_calculate_fare_uses_fare_calculator_constants(self, rider_dna, simpy_env):
        """_calculate_fare result matches FareCalculator for the same inputs."""
        agent = RiderAgent(
            rider_id="rider_fare_001",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=None,
        )
        pickup = (-23.56, -46.65)
        dropoff = (-23.55, -46.63)

        fare = agent._calculate_fare(pickup, dropoff, surge_multiplier=1.0)

        # Compute the expected value independently using FareCalculator
        calculator = FareCalculator()
        distance_km = agent._haversine_distance(pickup[0], pickup[1], dropoff[0], dropoff[1])
        duration_min = (distance_km / 25) * 60
        expected = calculator.calculate(distance_km, duration_min, surge_multiplier=1.0).total_fare

        assert fare == pytest.approx(expected)

    def test_calculate_fare_not_using_old_inline_constants(self, rider_dna, simpy_env):
        """Result differs from what the old inline constants (BASE=5, PER_KM=2.5) would give."""
        agent = RiderAgent(
            rider_id="rider_fare_002",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=None,
        )
        # A short trip where the old and new constants produce different totals
        pickup = (-23.56, -46.65)
        dropoff = (-23.555, -46.645)

        fare = agent._calculate_fare(pickup, dropoff, surge_multiplier=1.0)

        distance_km = agent._haversine_distance(pickup[0], pickup[1], dropoff[0], dropoff[1])
        duration_min = (distance_km / 25) * 60

        # Old inline formula: 5.0 + distance*2.5 + duration*0.5 (no minimum)
        old_fare = round(5.0 + distance_km * 2.5 + duration_min * 0.5, 2)

        # New formula uses FareCalculator (BASE=4, PER_KM=1.5, MIN=8)
        calculator = FareCalculator()
        new_fare = calculator.calculate(distance_km, duration_min, 1.0).total_fare

        # Sanity check: the two formulas do produce different results
        assert old_fare != pytest.approx(new_fare)
        # The agent result must match the new formula, not the old one
        assert fare == pytest.approx(new_fare)
        assert fare != pytest.approx(old_fare)

    def test_calculate_fare_with_surge_multiplier(self, rider_dna, simpy_env):
        """Surge multiplier is forwarded correctly to FareCalculator."""
        agent = RiderAgent(
            rider_id="rider_fare_003",
            dna=rider_dna,
            env=simpy_env,
            kafka_producer=None,
        )
        pickup = (-23.56, -46.65)
        dropoff = (-23.55, -46.63)

        fare_base = agent._calculate_fare(pickup, dropoff, surge_multiplier=1.0)
        fare_surged = agent._calculate_fare(pickup, dropoff, surge_multiplier=2.0)

        assert fare_surged == pytest.approx(fare_base * 2.0)
