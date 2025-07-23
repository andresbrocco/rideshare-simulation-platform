"""Tests for SQLite schema definition."""

import json
import os

import pytest
from sqlalchemy import inspect

from src.agents.dna import DriverDNA, RiderDNA, ShiftPreference
from src.db.database import init_database
from src.db.schema import Driver, Rider, SimulationMetadata, Trip
from src.trip import TripState


class TestDatabaseCreation:
    """Test database creation."""

    def test_database_creation(self, temp_sqlite_db):
        """Creates database with all tables."""
        session_maker = init_database(str(temp_sqlite_db))
        assert os.path.exists(temp_sqlite_db)

        inspector = inspect(session_maker.kw["bind"])
        tables = inspector.get_table_names()

        assert "drivers" in tables
        assert "riders" in tables
        assert "trips" in tables
        assert "simulation_metadata" in tables


class TestDriversTable:
    """Test drivers table schema."""

    def test_drivers_table_exists(self, temp_sqlite_db):
        """Drivers table has correct schema."""
        session_maker = init_database(str(temp_sqlite_db))
        inspector = inspect(session_maker.kw["bind"])

        columns = {col["name"]: col for col in inspector.get_columns("drivers")}

        assert "id" in columns
        assert "dna_json" in columns
        assert "current_location" in columns
        assert "status" in columns
        assert "active_trip" in columns
        assert "current_rating" in columns
        assert "rating_count" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        assert columns["id"]["primary_key"] == 1


class TestRidersTable:
    """Test riders table schema."""

    def test_riders_table_exists(self, temp_sqlite_db):
        """Riders table has correct schema."""
        session_maker = init_database(str(temp_sqlite_db))
        inspector = inspect(session_maker.kw["bind"])

        columns = {col["name"]: col for col in inspector.get_columns("riders")}

        assert "id" in columns
        assert "dna_json" in columns
        assert "current_location" in columns
        assert "status" in columns
        assert "active_trip" in columns
        assert "current_rating" in columns
        assert "rating_count" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        assert columns["id"]["primary_key"] == 1


class TestTripsTable:
    """Test trips table schema."""

    def test_trips_table_exists(self, temp_sqlite_db):
        """Trips table has correct schema."""
        session_maker = init_database(str(temp_sqlite_db))
        inspector = inspect(session_maker.kw["bind"])

        columns = {col["name"]: col for col in inspector.get_columns("trips")}

        assert "trip_id" in columns
        assert "rider_id" in columns
        assert "driver_id" in columns
        assert "state" in columns
        assert "pickup_location" in columns
        assert "dropoff_location" in columns
        assert "pickup_zone_id" in columns
        assert "dropoff_zone_id" in columns
        assert "surge_multiplier" in columns
        assert "fare" in columns
        assert "offer_sequence" in columns
        assert "cancelled_by" in columns
        assert "cancellation_reason" in columns
        assert "cancellation_stage" in columns
        assert "requested_at" in columns
        assert "matched_at" in columns
        assert "started_at" in columns
        assert "completed_at" in columns
        assert "updated_at" in columns

        assert columns["trip_id"]["primary_key"] == 1


class TestMetadataTable:
    """Test simulation metadata table."""

    def test_metadata_table_exists(self, temp_sqlite_db):
        """Simulation metadata table exists."""
        session_maker = init_database(str(temp_sqlite_db))
        inspector = inspect(session_maker.kw["bind"])

        columns = {col["name"]: col for col in inspector.get_columns("simulation_metadata")}

        assert "key" in columns
        assert "value" in columns
        assert "updated_at" in columns

        assert columns["key"]["primary_key"] == 1


class TestDriverDNASerialization:
    """Test driver DNA JSON serialization."""

    def test_driver_dna_json_serialization(self, temp_sqlite_db):
        """Stores DriverDNA as JSON."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.85,
            cancellation_tendency=0.05,
            service_quality=0.92,
            response_time=5.0,
            min_rider_rating=3.5,
            home_location=(-23.5505, -46.6333),
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
            email="joao.silva@email.com",
            phone="+5511987654321",
        )

        driver = Driver(
            id="d1",
            dna_json=driver_dna.model_dump_json(),
            current_location="-23.5505,-46.6333",
            status="available",
        )

        with session_maker() as session:
            session.add(driver)
            session.commit()

            retrieved = session.query(Driver).filter_by(id="d1").first()
            assert retrieved is not None
            assert retrieved.id == "d1"

            retrieved_dna = DriverDNA.model_validate_json(retrieved.dna_json)
            assert retrieved_dna.acceptance_rate == 0.85
            assert retrieved_dna.first_name == "João"
            assert retrieved_dna.vehicle_make == "Toyota"


class TestRiderDNASerialization:
    """Test rider DNA JSON serialization."""

    def test_rider_dna_json_serialization(self, temp_sqlite_db):
        """Stores RiderDNA as JSON."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=180,
            max_surge_multiplier=2.0,
            avg_rides_per_week=5,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Home", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Maria",
            last_name="Santos",
            email="maria.santos@email.com",
            phone="+5511912345678",
            payment_method_type="credit_card",
            payment_method_masked="**** 1234",
        )

        rider = Rider(
            id="r1",
            dna_json=rider_dna.model_dump_json(),
            current_location="-23.5505,-46.6333",
            status="idle",
        )

        with session_maker() as session:
            session.add(rider)
            session.commit()

            retrieved = session.query(Rider).filter_by(id="r1").first()
            assert retrieved is not None
            assert retrieved.id == "r1"

            retrieved_dna = RiderDNA.model_validate_json(retrieved.dna_json)
            assert retrieved_dna.behavior_factor == 0.75
            assert retrieved_dna.first_name == "Maria"
            assert retrieved_dna.payment_method_type == "credit_card"


class TestDriverLocationStorage:
    """Test driver location tuple storage."""

    def test_driver_location_tuple_storage(self, temp_sqlite_db):
        """Stores location as lat/lon tuple."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.9,
            cancellation_tendency=0.03,
            service_quality=0.95,
            response_time=4.0,
            min_rider_rating=4.0,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_1"],
            shift_preference=ShiftPreference.AFTERNOON,
            avg_hours_per_day=10,
            avg_days_per_week=6,
            vehicle_make="Honda",
            vehicle_model="Civic",
            vehicle_year=2021,
            license_plate="XYZ-5678",
            first_name="Carlos",
            last_name="Oliveira",
            email="carlos@email.com",
            phone="+5511999887766",
        )

        driver = Driver(
            id="d2",
            dna_json=driver_dna.model_dump_json(),
            current_location="-23.5629,-46.6544",
            status="on_trip",
        )

        with session_maker() as session:
            session.add(driver)
            session.commit()

            retrieved = session.query(Driver).filter_by(id="d2").first()
            assert retrieved is not None

            lat, lon = map(float, retrieved.current_location.split(","))
            assert lat == -23.5629
            assert lon == -46.6544


class TestTripStateEnumStorage:
    """Test trip state enum storage."""

    def test_trip_state_enum_storage(self, temp_sqlite_db):
        """Stores TripState enum."""
        session_maker = init_database(str(temp_sqlite_db))

        trip = Trip(
            trip_id="t1",
            rider_id="r1",
            driver_id="d1",
            state=TripState.MATCHED.value,
            pickup_location="-23.5505,-46.6333",
            dropoff_location="-23.5629,-46.6544",
            pickup_zone_id="zone_1",
            dropoff_zone_id="zone_2",
            surge_multiplier=1.5,
            fare=25.50,
            offer_sequence=1,
        )

        with session_maker() as session:
            session.add(trip)
            session.commit()

            retrieved = session.query(Trip).filter_by(trip_id="t1").first()
            assert retrieved is not None
            assert retrieved.state == TripState.MATCHED.value
            assert TripState(retrieved.state) == TripState.MATCHED


class TestIndexesCreated:
    """Test indexes exist for query performance."""

    def test_indexes_created(self, temp_sqlite_db):
        """Indexes exist for query performance."""
        session_maker = init_database(str(temp_sqlite_db))
        inspector = inspect(session_maker.kw["bind"])

        driver_indexes = inspector.get_indexes("drivers")
        driver_index_names = [idx["name"] for idx in driver_indexes]
        assert "idx_driver_status" in driver_index_names

        rider_indexes = inspector.get_indexes("riders")
        rider_index_names = [idx["name"] for idx in rider_indexes]
        assert "idx_rider_status" in rider_index_names

        trip_indexes = inspector.get_indexes("trips")
        trip_index_names = [idx["name"] for idx in trip_indexes]
        assert "idx_trip_state" in trip_index_names
        assert "idx_trip_driver" in trip_index_names
        assert "idx_trip_rider" in trip_index_names


class TestSchemaMigrationSupport:
    """Test schema version tracking."""

    def test_schema_migration_support(self, temp_sqlite_db):
        """Schema version tracked."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            metadata = session.query(SimulationMetadata).filter_by(key="schema_version").first()
            assert metadata is not None
            assert metadata.value == "1.0.0"
