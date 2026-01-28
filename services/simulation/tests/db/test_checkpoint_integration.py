"""Integration tests for checkpoint save/restore with full engine lifecycle.

These tests verify the complete checkpoint flow:
1. Create engine with real agents
2. Save checkpoint (via engine.save_checkpoint or pause)
3. Create NEW engine instance
4. Restore from checkpoint
5. Verify state matches and simulation can continue
"""

# ruff: noqa: E402
# E402 is intentionally suppressed because we need to set up module aliases
# before importing the modules that depend on them.

import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
import simpy

# IMPORTANT: Pre-import modules and create aliases to fix relative import issues.
# The engine uses `from db.checkpoint import ...` without `src.` prefix,
# but checkpoint.py has relative imports like `from ..agents.dna import ...`.
# By aliasing `db` -> `src.db`, we make these imports work correctly.
from src.db import checkpoint as _checkpoint_module
from src.db import database as _database_module
from src.db import repositories as _repositories_module

sys.modules["db"] = sys.modules["src.db"]
sys.modules["db.checkpoint"] = _checkpoint_module
sys.modules["db.database"] = _database_module
sys.modules["db.repositories"] = _repositories_module

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.agents.driver_agent import DriverAgent
from src.agents.rider_agent import RiderAgent
from src.db.checkpoint import CheckpointManager
from src.db.database import init_database
from src.db.repositories.trip_repository import TripRepository
from src.engine import SimulationEngine, SimulationState
from src.matching.driver_geospatial_index import DriverGeospatialIndex
from src.matching.matching_server import MatchingServer
from src.trip import Trip, TripState


def create_driver_dna(seed: int = 0) -> DriverDNA:
    """Create a DriverDNA with deterministic values based on seed."""
    return DriverDNA(
        acceptance_rate=0.85,
        cancellation_tendency=0.05,
        service_quality=0.9,
        response_time=5.0,
        min_rider_rating=3.5,
        surge_acceptance_modifier=1.5,
        home_location=(-23.55 + seed * 0.001, -46.63 + seed * 0.001),
        preferred_zones=["BVI", "PIN"],
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020 + seed,
        license_plate=f"ABC-{1000 + seed}",
        first_name=f"Driver{seed}",
        last_name="Test",
        email=f"driver{seed}@test.com",
        phone=f"+551199999{seed:04d}",
    )


def create_rider_dna(seed: int = 0) -> RiderDNA:
    """Create a RiderDNA with deterministic values based on seed."""
    return RiderDNA(
        behavior_factor=0.75,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=5,
        frequent_destinations=[
            {"coordinates": (-23.565, -46.695), "weight": 0.6},
            {"coordinates": (-23.55, -46.635), "weight": 0.4},
        ],
        home_location=(-23.56 + seed * 0.001, -46.65 + seed * 0.001),
        first_name=f"Rider{seed}",
        last_name="Test",
        email=f"rider{seed}@test.com",
        phone=f"+551198888{seed:04d}",
        payment_method_type="credit_card",
        payment_method_masked="**** 1234",
    )


def create_matching_server(env: simpy.Environment) -> MatchingServer:
    """Create a MatchingServer with mocked external dependencies."""
    driver_index = Mock(spec=DriverGeospatialIndex)
    driver_index.find_nearest_drivers = Mock(return_value=[])
    driver_index._driver_locations = {}

    notification_dispatch = Mock()
    notification_dispatch.send_driver_offer = Mock(return_value=True)

    osrm_client = Mock()
    osrm_client.get_route = AsyncMock()

    kafka_producer = Mock()
    kafka_producer.produce = Mock()

    return MatchingServer(
        env=env,
        driver_index=driver_index,
        notification_dispatch=notification_dispatch,
        osrm_client=osrm_client,
        kafka_producer=kafka_producer,
    )


def create_engine(
    sqlite_session_maker,
    env: simpy.Environment | None = None,
    matching_server: MatchingServer | None = None,
) -> SimulationEngine:
    """Create a SimulationEngine with real components except external services."""
    if env is None:
        env = simpy.Environment()

    if matching_server is None:
        matching_server = create_matching_server(env)

    kafka_producer = Mock()
    kafka_producer.produce = Mock()

    redis_client = Mock()
    osrm_client = Mock()

    engine = SimulationEngine(
        env=env,
        matching_server=matching_server,
        kafka_producer=kafka_producer,
        redis_client=redis_client,
        osrm_client=osrm_client,
        sqlite_db=sqlite_session_maker,
        simulation_start_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
    )
    # Use maximum speed to avoid wall-clock delays
    engine._speed_multiplier = 100

    return engine


def create_driver_agent(
    driver_id: str,
    dna: DriverDNA,
    env: simpy.Environment,
    engine: SimulationEngine,
) -> DriverAgent:
    """Create a DriverAgent attached to the engine."""
    return DriverAgent(
        driver_id=driver_id,
        dna=dna,
        env=env,
        kafka_producer=engine._kafka_producer,
        redis_publisher=engine._redis_client,
        driver_repository=None,
        registry_manager=None,
        simulation_engine=engine,
        immediate_online=False,
        puppet=True,  # Use puppet mode to avoid complex async behavior
    )


def create_rider_agent(
    rider_id: str,
    dna: RiderDNA,
    env: simpy.Environment,
    engine: SimulationEngine,
) -> RiderAgent:
    """Create a RiderAgent attached to the engine."""
    return RiderAgent(
        rider_id=rider_id,
        dna=dna,
        env=env,
        kafka_producer=engine._kafka_producer,
        redis_publisher=engine._redis_client,
        rider_repository=None,
        simulation_engine=engine,
        immediate_first_trip=False,
        puppet=True,  # Use puppet mode to avoid complex async behavior
    )


class TestCleanCheckpointIntegration:
    """Integration tests for clean (graceful) checkpoint recovery."""

    def test_clean_checkpoint_full_recovery(self, temp_sqlite_db):
        """Full lifecycle: create agents → pause → checkpoint → restore → verify.

        This tests the happy path where:
        1. Simulation runs with agents
        2. Graceful pause (no in-flight trips)
        3. Checkpoint is created
        4. New engine restores from checkpoint
        5. State matches original
        """
        session_maker = init_database(str(temp_sqlite_db))

        # === Phase 1: Create and run initial engine ===
        engine1 = create_engine(session_maker)

        # Create drivers with distinct state
        drivers_data = []
        for i in range(3):
            dna = create_driver_dna(seed=i)
            driver = create_driver_agent(f"driver_{i}", dna, engine1._env, engine1)
            driver._status = "online"
            driver._location = (-23.55 + i * 0.01, -46.63 + i * 0.01)
            driver._current_rating = 4.5 + i * 0.1
            driver._rating_count = 10 + i
            engine1.register_driver(driver)
            engine1._matching_server.register_driver(driver)
            drivers_data.append(
                {
                    "id": driver.driver_id,
                    "status": driver._status,
                    "location": driver._location,
                    "rating": driver._current_rating,
                    "rating_count": driver._rating_count,
                }
            )

        # Create riders with distinct state
        riders_data = []
        for i in range(5):
            dna = create_rider_dna(seed=i)
            rider = create_rider_agent(f"rider_{i}", dna, engine1._env, engine1)
            rider._status = "waiting" if i < 2 else "offline"
            rider._location = (-23.56 + i * 0.01, -46.65 + i * 0.01)
            rider._current_rating = 4.8 - i * 0.05
            rider._rating_count = 5 + i
            engine1.register_rider(rider)
            riders_data.append(
                {
                    "id": rider.rider_id,
                    "status": rider._status,
                    "location": rider._location,
                    "rating": rider._current_rating,
                    "rating_count": rider._rating_count,
                }
            )

        # Advance simulation time
        engine1.start()
        engine1.step(1000)  # Advance 1000 simulated seconds

        original_time = engine1._env.now
        original_driver_count = len(engine1._active_drivers)
        original_rider_count = len(engine1._active_riders)

        # === Phase 2: Save checkpoint ===
        engine1.save_checkpoint()

        # Verify checkpoint was created as graceful (no in-flight trips)
        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info is not None
            assert info["checkpoint_type"] == "graceful"
            assert info["in_flight_trips"] == 0
            assert info["current_time"] == original_time

        # === Phase 3: Create new engine and restore ===
        engine2 = create_engine(session_maker)

        # Verify engine2 starts fresh
        assert engine2._env.now == 0
        assert len(engine2._active_drivers) == 0
        assert len(engine2._active_riders) == 0

        # Restore from checkpoint
        success = engine2.try_restore_from_checkpoint()
        assert success is True

        # === Phase 4: Verify restored state matches original ===

        # Time should match
        assert engine2._env.now == original_time

        # Agent counts should match
        assert len(engine2._active_drivers) == original_driver_count
        assert len(engine2._active_riders) == original_rider_count

        # Verify each driver's state was restored
        for expected in drivers_data:
            driver = engine2._active_drivers.get(expected["id"])
            assert driver is not None, f"Driver {expected['id']} not restored"
            assert driver._status == expected["status"]
            assert driver._location == expected["location"]
            assert driver._current_rating == expected["rating"]
            assert driver._rating_count == expected["rating_count"]

        # Verify each rider's state was restored
        for expected in riders_data:
            rider = engine2._active_riders.get(expected["id"])
            assert rider is not None, f"Rider {expected['id']} not restored"
            assert rider._status == expected["status"]
            assert rider._location == expected["location"]
            assert rider._current_rating == expected["rating"]
            assert rider._rating_count == expected["rating_count"]

        # Verify drivers are registered with matching server
        for driver_id in engine2._active_drivers:
            assert driver_id in engine2._matching_server._drivers

        # === Phase 5: Verify simulation can continue ===
        # Should be able to step without errors
        engine2.step(100)
        assert engine2._env.now == original_time + 100


class TestDirtyCheckpointIntegration:
    """Integration tests for dirty (crash) checkpoint recovery."""

    def test_dirty_checkpoint_full_recovery(self, temp_sqlite_db, caplog):
        """Full lifecycle with in-flight trips: create → run with trips → checkpoint → restore.

        This tests the crash recovery path where:
        1. Simulation runs with agents and active trips
        2. Checkpoint created with in-flight trips (dirty)
        3. New engine restores from checkpoint
        4. In-flight trips are cancelled
        5. Warning is logged about dirty checkpoint
        """
        import logging

        session_maker = init_database(str(temp_sqlite_db))

        # === Phase 1: Create engine with agents ===
        engine1 = create_engine(session_maker)

        # Create drivers
        for i in range(3):
            dna = create_driver_dna(seed=i)
            driver = create_driver_agent(f"driver_{i}", dna, engine1._env, engine1)
            driver._status = "online" if i < 2 else "en_route_pickup"
            driver._location = (-23.55 + i * 0.01, -46.63 + i * 0.01)
            driver._active_trip = f"trip_{i}" if i == 2 else None
            engine1.register_driver(driver)
            engine1._matching_server.register_driver(driver)

        # Create riders
        for i in range(3):
            dna = create_rider_dna(seed=i)
            rider = create_rider_agent(f"rider_{i}", dna, engine1._env, engine1)
            rider._status = "in_trip" if i == 0 else "waiting"
            rider._location = (-23.56 + i * 0.01, -46.65 + i * 0.01)
            rider._active_trip = "trip_0" if i == 0 else None
            engine1.register_rider(rider)

        # === Phase 2: Create in-flight trips ===
        # Create Trip domain objects and register with matching server
        trip_0 = Trip(
            trip_id="trip_0",
            rider_id="rider_0",
            driver_id="driver_2",
            state=TripState.MATCHED,
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.65),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.0,
            fare=20.0,
        )
        engine1._matching_server._active_trips["trip_0"] = trip_0

        trip_1 = Trip(
            trip_id="trip_1",
            rider_id="rider_1",
            driver_id="driver_1",
            state=TripState.STARTED,
            pickup_location=(-23.55, -46.63),
            dropoff_location=(-23.56, -46.65),
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.5,
            fare=25.0,
        )
        engine1._matching_server._active_trips["trip_1"] = trip_1

        # Also persist trips to database for restore to load them
        with session_maker() as session:
            trip_repo = TripRepository(session)

            trip_repo.create(
                trip_id="trip_0",
                rider_id="rider_0",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.0,
            )
            trip_repo.update_state("trip_0", TripState.MATCHED, driver_id="driver_2")

            trip_repo.create(
                trip_id="trip_1",
                rider_id="rider_1",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.5,
                fare=25.0,
            )
            trip_repo.update_state("trip_1", TripState.MATCHED, driver_id="driver_1")
            trip_repo.update_state("trip_1", TripState.DRIVER_EN_ROUTE)
            trip_repo.update_state("trip_1", TripState.DRIVER_ARRIVED)
            trip_repo.update_state("trip_1", TripState.STARTED)

            # Completed trip (not in-flight, should be ignored)
            trip_repo.create(
                trip_id="trip_completed",
                rider_id="rider_2",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=15.0,
            )
            trip_repo.update_state(
                "trip_completed", TripState.MATCHED, driver_id="driver_0"
            )
            trip_repo.update_state("trip_completed", TripState.DRIVER_EN_ROUTE)
            trip_repo.update_state("trip_completed", TripState.DRIVER_ARRIVED)
            trip_repo.update_state("trip_completed", TripState.STARTED)
            trip_repo.update_state("trip_completed", TripState.COMPLETED)

            session.commit()

        # Start engine and advance time
        engine1.start()
        engine1.step(500)

        original_time = engine1._env.now
        original_driver_count = len(engine1._active_drivers)
        original_rider_count = len(engine1._active_riders)

        # === Phase 3: Save checkpoint (should be dirty) ===
        engine1.save_checkpoint()

        # Verify checkpoint is dirty
        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info is not None
            assert info["checkpoint_type"] == "crash"
            assert info["in_flight_trips"] == 2  # trip_0 (MATCHED) and trip_1 (STARTED)

        # === Phase 4: Create new engine and restore ===
        engine2 = create_engine(session_maker)

        # Restore from checkpoint with logging capture
        with caplog.at_level(logging.WARNING):
            success = engine2.try_restore_from_checkpoint()

        assert success is True

        # === Phase 5: Verify dirty checkpoint behavior ===

        # Should have logged warning about dirty checkpoint
        dirty_warning_found = any(
            "dirty checkpoint" in record.message.lower() for record in caplog.records
        )
        assert dirty_warning_found, "Expected warning about dirty checkpoint"

        # Time should be restored
        assert engine2._env.now == original_time

        # Agent counts should match
        assert len(engine2._active_drivers) == original_driver_count
        assert len(engine2._active_riders) == original_rider_count

        # In-flight trips should have been cancelled during restore
        # (restore_to_engine cancels them to prevent inconsistent state)
        active_trips = engine2._matching_server.get_active_trips()
        assert (
            len(active_trips) == 0
        ), "In-flight trips should be cancelled on dirty restore"

        # === Phase 6: Verify simulation can continue after dirty restore ===
        engine2.step(100)
        assert engine2._env.now == original_time + 100


class TestCheckpointMetadataPreservation:
    """Tests for preserving engine metadata across checkpoint/restore."""

    def test_speed_multiplier_preserved(self, temp_sqlite_db):
        """Speed multiplier is preserved across checkpoint/restore."""
        session_maker = init_database(str(temp_sqlite_db))

        engine1 = create_engine(session_maker)
        engine1._speed_multiplier = 50  # Custom speed

        # Add at least one agent so checkpoint has data
        dna = create_driver_dna(seed=0)
        driver = create_driver_agent("driver_0", dna, engine1._env, engine1)
        engine1.register_driver(driver)
        engine1._matching_server.register_driver(driver)

        engine1.start()
        engine1.step(100)
        engine1.save_checkpoint()

        engine2 = create_engine(session_maker)
        engine2.try_restore_from_checkpoint()

        assert engine2._speed_multiplier == 50

    def test_simulation_time_preserved(self, temp_sqlite_db):
        """Simulation time is exactly preserved across checkpoint/restore."""
        session_maker = init_database(str(temp_sqlite_db))

        engine1 = create_engine(session_maker)

        # Add agent
        dna = create_driver_dna(seed=0)
        driver = create_driver_agent("driver_0", dna, engine1._env, engine1)
        engine1.register_driver(driver)
        engine1._matching_server.register_driver(driver)

        engine1.start()
        engine1.step(12345)  # Specific time value

        original_time = engine1._env.now
        engine1.save_checkpoint()

        engine2 = create_engine(session_maker)
        engine2.try_restore_from_checkpoint()

        assert engine2._env.now == original_time
        assert engine2._env.now == 12345

    def test_matching_server_env_updated(self, temp_sqlite_db):
        """Matching server's environment reference is updated after restore."""
        session_maker = init_database(str(temp_sqlite_db))

        engine1 = create_engine(session_maker)

        dna = create_driver_dna(seed=0)
        driver = create_driver_agent("driver_0", dna, engine1._env, engine1)
        engine1.register_driver(driver)
        engine1._matching_server.register_driver(driver)

        engine1.start()
        engine1.step(100)
        engine1.save_checkpoint()

        engine2 = create_engine(session_maker)
        original_env = engine2._env

        engine2.try_restore_from_checkpoint()

        # Engine should have a new environment
        assert engine2._env is not original_env
        # Matching server should reference the same (new) environment
        assert engine2._matching_server._env is engine2._env
