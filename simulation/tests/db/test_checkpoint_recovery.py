"""Tests for checkpoint and recovery manager."""

import logging

import pytest

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.db.checkpoint import CheckpointManager
from src.db.database import init_database
from src.db.repositories.driver_repository import DriverRepository
from src.db.repositories.rider_repository import RiderRepository
from src.db.repositories.route_cache_repository import RouteCacheRepository
from src.db.repositories.trip_repository import TripRepository
from src.trip import TripState
from tests.factories import DNAFactory


class TestCheckpointMetadata:
    """Tests for checkpoint metadata operations."""

    def test_create_checkpoint_metadata(self, temp_sqlite_db):
        """Saves simulation metadata to checkpoint."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=86400.0,
                speed_multiplier=10,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info is not None
            assert info["current_time"] == 86400.0
            assert info["speed_multiplier"] == 10
            assert info["status"] == "PAUSED"
            assert info["checkpoint_version"] == "1.0.0"

    def test_checkpoint_versioning(self, temp_sqlite_db):
        """Tracks checkpoint version in metadata."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=1000.0,
                speed_multiplier=1,
                status="RUNNING",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info["checkpoint_version"] == "1.0.0"


class TestCheckpointAgents:
    """Tests for checkpoint agent persistence."""

    def test_create_checkpoint_all_agents(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Saves all drivers and riders to checkpoint."""
        session_maker = init_database(str(temp_sqlite_db))
        drivers = [
            ("d1", dna_factory.driver_dna()),
            ("d2", dna_factory.driver_dna()),
        ]
        riders = [
            ("r1", dna_factory.rider_dna()),
            ("r2", dna_factory.rider_dna()),
            ("r3", dna_factory.rider_dna()),
        ]

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=5000.0,
                speed_multiplier=1,
                status="RUNNING",
                drivers=drivers,
                riders=riders,
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            driver_repo = DriverRepository(session)
            rider_repo = RiderRepository(session)

            d1 = driver_repo.get("d1")
            d2 = driver_repo.get("d2")
            r1 = rider_repo.get("r1")
            r2 = rider_repo.get("r2")
            r3 = rider_repo.get("r3")

            assert d1 is not None
            assert d2 is not None
            assert r1 is not None
            assert r2 is not None
            assert r3 is not None

    def test_load_checkpoint_agents(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Restores all agents with deserialized DNA."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna(acceptance_rate=0.85)
        rider_dna = dna_factory.rider_dna(patience_threshold=180)

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=3000.0,
                speed_multiplier=10,
                status="PAUSED",
                drivers=[("d1", driver_dna)],
                riders=[("r1", rider_dna)],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert checkpoint is not None
            assert len(checkpoint["agents"]["drivers"]) == 1
            assert len(checkpoint["agents"]["riders"]) == 1

            driver = checkpoint["agents"]["drivers"][0]
            rider = checkpoint["agents"]["riders"][0]

            assert driver["id"] == "d1"
            assert driver["dna"]["acceptance_rate"] == 0.85
            assert rider["id"] == "r1"
            assert rider["dna"]["patience_threshold"] == 180


class TestCheckpointTrips:
    """Tests for checkpoint trip persistence."""

    def test_create_checkpoint_all_trips(self, temp_sqlite_db):
        """Saves all trip states to checkpoint."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            for i in range(3):
                trip_repo.create(
                    trip_id=f"trip_{i}",
                    rider_id=f"r{i}",
                    pickup_location=(-23.55, -46.63),
                    dropoff_location=(-23.56, -46.65),
                    pickup_zone_id="zone_1",
                    dropoff_zone_id="zone_2",
                    surge_multiplier=1.2,
                    fare=25.0,
                )
            session.commit()

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_repo.update_state("trip_0", TripState.MATCHED, driver_id="d1")
            trip_repo.update_state("trip_1", TripState.STARTED)
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=10000.0,
                speed_multiplier=1,
                status="DRAINING",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_0 = trip_repo.get("trip_0")
            trip_1 = trip_repo.get("trip_1")
            trip_2 = trip_repo.get("trip_2")

            assert trip_0.state == TripState.MATCHED
            assert trip_1.state == TripState.STARTED
            assert trip_2.state == TripState.REQUESTED

    def test_load_checkpoint_trips(self, temp_sqlite_db):
        """Restores trip states correctly."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_repo.create(
                trip_id="trip_test",
                rider_id="r1",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.5,
                fare=30.0,
            )
            trip_repo.update_state("trip_test", TripState.MATCHED, driver_id="d1")
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=5000.0,
                speed_multiplier=1,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert checkpoint is not None
            assert len(checkpoint["trips"]) == 1
            trip = checkpoint["trips"][0]
            assert trip.trip_id == "trip_test"
            assert trip.state == TripState.MATCHED
            assert trip.driver_id == "d1"


class TestCheckpointRouteCache:
    """Tests for checkpoint route cache persistence."""

    def test_create_checkpoint_route_cache(self, temp_sqlite_db):
        """Saves route cache to checkpoint."""
        session_maker = init_database(str(temp_sqlite_db))
        routes = {
            "h3_1|h3_2": {"distance": 1000.0, "duration": 300.0, "polyline": "encoded1"},
            "h3_3|h3_4": {"distance": 2000.0, "duration": 600.0, "polyline": "encoded2"},
        }

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=1000.0,
                speed_multiplier=1,
                status="RUNNING",
                drivers=[],
                riders=[],
                route_cache=routes,
            )
            session.commit()

        with session_maker() as session:
            route_repo = RouteCacheRepository(session)
            count = route_repo.count()
            assert count == 2

    def test_load_checkpoint_route_cache(self, temp_sqlite_db):
        """Pre-loads route cache on recovery."""
        session_maker = init_database(str(temp_sqlite_db))
        routes = {
            "h3_a|h3_b": {"distance": 1500.0, "duration": 450.0, "polyline": "enc_ab"},
        }

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=2000.0,
                speed_multiplier=10,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache=routes,
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert "h3_a|h3_b" in checkpoint["route_cache"]
            cached = checkpoint["route_cache"]["h3_a|h3_b"]
            assert cached["distance"] == 1500.0
            assert cached["duration"] == 450.0


class TestCheckpointAtomicity:
    """Tests for checkpoint atomicity."""

    def test_create_checkpoint_atomic(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Checkpoint is atomic - all or nothing."""
        session_maker = init_database(str(temp_sqlite_db))
        drivers = [("d1", dna_factory.driver_dna())]

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=1000.0,
                speed_multiplier=1,
                status="RUNNING",
                drivers=drivers,
                riders=[],
                route_cache={},
            )
            # Rollback instead of commit
            session.rollback()

        with session_maker() as session:
            driver_repo = DriverRepository(session)
            d1 = driver_repo.get("d1")
            assert d1 is None  # Nothing persisted on rollback


class TestCleanVsDirtyCheckpoint:
    """Tests for clean vs dirty checkpoint detection."""

    def test_checkpoint_clean_vs_dirty_clean(self, temp_sqlite_db):
        """Detects clean checkpoint (no in-flight trips)."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_repo.create(
                trip_id="completed_trip",
                rider_id="r1",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.0,
            )
            trip_repo.update_state("completed_trip", TripState.COMPLETED)
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=5000.0,
                speed_multiplier=1,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            assert manager.is_clean_checkpoint() is True
            info = manager.get_checkpoint_info()
            assert info["checkpoint_type"] == "graceful"
            assert info["in_flight_trips"] == 0

    def test_checkpoint_clean_vs_dirty_dirty(self, temp_sqlite_db):
        """Detects dirty checkpoint (has in-flight trips)."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            for i in range(5):
                trip_repo.create(
                    trip_id=f"inflight_{i}",
                    rider_id=f"r{i}",
                    pickup_location=(-23.55, -46.63),
                    dropoff_location=(-23.56, -46.65),
                    pickup_zone_id="zone_1",
                    dropoff_zone_id="zone_2",
                    surge_multiplier=1.0,
                    fare=20.0,
                )
            trip_repo.update_state("inflight_0", TripState.MATCHED, driver_id="d1")
            trip_repo.update_state("inflight_1", TripState.STARTED)
            trip_repo.update_state("inflight_2", TripState.COMPLETED)
            trip_repo.update_state(
                "inflight_3",
                TripState.CANCELLED,
                cancelled_by="rider",
                cancellation_reason="test",
                cancellation_stage="requested",
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=8000.0,
                speed_multiplier=1,
                status="DRAINING",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            assert manager.is_clean_checkpoint() is False
            info = manager.get_checkpoint_info()
            assert info["checkpoint_type"] == "crash"
            assert info["in_flight_trips"] == 3  # inflight_0, inflight_1, inflight_4

    def test_graceful_pause_checkpoint(self, temp_sqlite_db):
        """Creates clean checkpoint after drain completes."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_repo.create(
                trip_id="trip1",
                rider_id="r1",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.0,
            )
            trip_repo.create(
                trip_id="trip2",
                rider_id="r2",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=25.0,
            )
            trip_repo.update_state("trip1", TripState.COMPLETED)
            trip_repo.update_state(
                "trip2",
                TripState.CANCELLED,
                cancelled_by="system",
                cancellation_reason="timeout",
                cancellation_stage="matched",
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=10000.0,
                speed_multiplier=1,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info["checkpoint_type"] == "graceful"
            assert info["in_flight_trips"] == 0

    def test_crash_checkpoint(self, temp_sqlite_db):
        """Creates dirty checkpoint with in-flight trips."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            for i in range(3):
                trip_repo.create(
                    trip_id=f"crash_trip_{i}",
                    rider_id=f"r{i}",
                    pickup_location=(-23.55, -46.63),
                    dropoff_location=(-23.56, -46.65),
                    pickup_zone_id="zone_1",
                    dropoff_zone_id="zone_2",
                    surge_multiplier=1.0,
                    fare=20.0,
                )
            trip_repo.update_state("crash_trip_0", TripState.MATCHED, driver_id="d1")
            trip_repo.update_state("crash_trip_1", TripState.MATCHED, driver_id="d2")
            trip_repo.update_state("crash_trip_2", TripState.MATCHED, driver_id="d3")
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=5000.0,
                speed_multiplier=1,
                status="RUNNING",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            info = manager.get_checkpoint_info()
            assert info["checkpoint_type"] == "crash"
            assert info["in_flight_trips"] == 3


class TestCheckpointRecovery:
    """Tests for checkpoint recovery scenarios."""

    def test_resume_from_clean_checkpoint(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Resumes from clean checkpoint without warnings."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=50000.0,
                speed_multiplier=100,
                status="PAUSED",
                drivers=[("d1", dna_factory.driver_dna())],
                riders=[("r1", dna_factory.rider_dna())],
                route_cache={"h3_x|h3_y": {"distance": 500.0, "duration": 150.0, "polyline": None}},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert checkpoint is not None
            assert checkpoint["metadata"]["current_time"] == 50000.0
            assert checkpoint["metadata"]["speed_multiplier"] == 100
            assert checkpoint["metadata"]["status"] == "PAUSED"
            assert checkpoint["metadata"]["checkpoint_type"] == "graceful"
            assert len(checkpoint["agents"]["drivers"]) == 1
            assert len(checkpoint["agents"]["riders"]) == 1

    def test_resume_from_dirty_checkpoint(self, temp_sqlite_db, caplog):
        """Warns about potential duplicates on dirty checkpoint resume."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            trip_repo = TripRepository(session)
            trip_repo.create(
                trip_id="dirty_trip",
                rider_id="r1",
                pickup_location=(-23.55, -46.63),
                dropoff_location=(-23.56, -46.65),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.0,
            )
            trip_repo.update_state("dirty_trip", TripState.STARTED)
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=30000.0,
                speed_multiplier=10,
                status="RUNNING",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with caplog.at_level(logging.WARNING), session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert checkpoint is not None
            assert checkpoint["metadata"]["checkpoint_type"] == "crash"
            assert (
                "dirty checkpoint" in caplog.text.lower()
                or "potential duplicate" in caplog.text.lower()
            )

    def test_load_nonexistent_checkpoint(self, temp_sqlite_db):
        """Handles missing checkpoint gracefully."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()
            assert checkpoint is None


class TestLoadCheckpointMetadata:
    """Tests for loading checkpoint metadata."""

    def test_load_checkpoint_metadata(self, temp_sqlite_db):
        """Restores simulation metadata from checkpoint."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=172800.0,
                speed_multiplier=100,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            checkpoint = manager.load_checkpoint()

            assert checkpoint is not None
            assert checkpoint["metadata"]["current_time"] == 172800.0
            assert checkpoint["metadata"]["speed_multiplier"] == 100
            assert checkpoint["metadata"]["status"] == "PAUSED"


class TestHasCheckpoint:
    """Tests for has_checkpoint method."""

    def test_has_checkpoint_true(self, temp_sqlite_db):
        """Returns True when checkpoint exists."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            manager.create_checkpoint(
                current_time=1000.0,
                speed_multiplier=1,
                status="PAUSED",
                drivers=[],
                riders=[],
                route_cache={},
            )
            session.commit()

        with session_maker() as session:
            manager = CheckpointManager(session)
            assert manager.has_checkpoint() is True

    def test_has_checkpoint_false(self, temp_sqlite_db):
        """Returns False when no checkpoint exists."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            manager = CheckpointManager(session)
            assert manager.has_checkpoint() is False


class TestCheckpointError:
    """Tests for CheckpointError exception."""

    def test_checkpoint_error_import(self):
        """CheckpointError can be imported from checkpoint module."""
        from src.db.checkpoint import CheckpointError

        error = CheckpointError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
