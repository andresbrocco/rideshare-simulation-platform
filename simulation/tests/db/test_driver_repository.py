"""Tests for driver repository CRUD operations."""

import pytest
from sqlalchemy import select

from src.agents.dna import DriverDNA, ShiftPreference
from src.db.database import init_database
from src.db.repositories.driver_repository import DriverRepository
from src.db.schema import Driver


class TestDriverRepository:
    """Test driver repository CRUD operations."""

    def test_create_driver(self, temp_sqlite_db):
        """Creates driver with DNA."""
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

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d1", driver_dna)
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d1")
            assert driver is not None
            assert driver.id == "d1"
            assert driver.status == "offline"
            assert driver.current_location == "-23.5505,-46.6333"

            retrieved_dna = DriverDNA.model_validate_json(driver.dna_json)
            assert retrieved_dna.acceptance_rate == 0.85
            assert retrieved_dna.first_name == "João"

    def test_get_driver_by_id(self, temp_sqlite_db):
        """Retrieves driver by ID."""
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

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d2", driver_dna)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            driver = repo.get("d2")
            assert driver is not None
            assert driver.id == "d2"

    def test_get_driver_not_found(self, temp_sqlite_db):
        """Returns None for missing driver."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = DriverRepository(session)
            driver = repo.get("nonexistent")
            assert driver is None

    def test_update_driver_location(self, temp_sqlite_db):
        """Updates driver location only (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.8,
            cancellation_tendency=0.1,
            service_quality=0.85,
            response_time=6.0,
            min_rider_rating=3.0,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_1"],
            shift_preference=ShiftPreference.EVENING,
            avg_hours_per_day=6,
            avg_days_per_week=4,
            vehicle_make="Chevrolet",
            vehicle_model="Onix",
            vehicle_year=2019,
            license_plate="DEF-9012",
            first_name="Ana",
            last_name="Costa",
            email="ana@email.com",
            phone="+5511988776655",
        )

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d3", driver_dna)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.update_location("d3", (-23.5629, -46.6544))
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d3")
            assert driver.current_location == "-23.5629,-46.6544"

            retrieved_dna = DriverDNA.model_validate_json(driver.dna_json)
            assert retrieved_dna.acceptance_rate == 0.8

    def test_update_driver_status(self, temp_sqlite_db):
        """Updates driver status (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.88,
            cancellation_tendency=0.04,
            service_quality=0.91,
            response_time=5.5,
            min_rider_rating=3.8,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_2"],
            shift_preference=ShiftPreference.NIGHT,
            avg_hours_per_day=7,
            avg_days_per_week=5,
            vehicle_make="Volkswagen",
            vehicle_model="Gol",
            vehicle_year=2018,
            license_plate="GHI-3456",
            first_name="Pedro",
            last_name="Almeida",
            email="pedro@email.com",
            phone="+5511977665544",
        )

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d4", driver_dna)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.update_status("d4", "available")
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d4")
            assert driver.status == "available"

            retrieved_dna = DriverDNA.model_validate_json(driver.dna_json)
            assert retrieved_dna.acceptance_rate == 0.88

    def test_update_driver_rating(self, temp_sqlite_db):
        """Updates driver rating (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.82,
            cancellation_tendency=0.06,
            service_quality=0.87,
            response_time=7.0,
            min_rider_rating=3.2,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_1", "zone_3"],
            shift_preference=ShiftPreference.FLEXIBLE,
            avg_hours_per_day=9,
            avg_days_per_week=6,
            vehicle_make="Fiat",
            vehicle_model="Argo",
            vehicle_year=2022,
            license_plate="JKL-7890",
            first_name="Lucas",
            last_name="Ferreira",
            email="lucas@email.com",
            phone="+5511966554433",
        )

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d5", driver_dna)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.update_rating("d5", 4.5, 10)
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d5")
            assert driver.current_rating == 4.5
            assert driver.rating_count == 10

            retrieved_dna = DriverDNA.model_validate_json(driver.dna_json)
            assert retrieved_dna.acceptance_rate == 0.82

    def test_update_active_trip(self, temp_sqlite_db):
        """Links driver to active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.9,
            cancellation_tendency=0.02,
            service_quality=0.96,
            response_time=3.5,
            min_rider_rating=4.2,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_1"],
            shift_preference=ShiftPreference.MORNING,
            avg_hours_per_day=8,
            avg_days_per_week=5,
            vehicle_make="Toyota",
            vehicle_model="Prius",
            vehicle_year=2023,
            license_plate="MNO-2468",
            first_name="Rafael",
            last_name="Martins",
            email="rafael@email.com",
            phone="+5511955443322",
        )

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d6", driver_dna)
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.update_active_trip("d6", "trip123")
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d6")
            assert driver.active_trip == "trip123"

    def test_clear_active_trip(self, temp_sqlite_db):
        """Clears driver active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = DriverDNA(
            acceptance_rate=0.87,
            cancellation_tendency=0.05,
            service_quality=0.90,
            response_time=5.0,
            min_rider_rating=3.5,
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_2"],
            shift_preference=ShiftPreference.AFTERNOON,
            avg_hours_per_day=7,
            avg_days_per_week=5,
            vehicle_make="Nissan",
            vehicle_model="Versa",
            vehicle_year=2021,
            license_plate="PQR-1357",
            first_name="Bruno",
            last_name="Sousa",
            email="bruno@email.com",
            phone="+5511944332211",
        )

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d7", driver_dna)
            repo.update_active_trip("d7", "trip456")
            session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.update_active_trip("d7", None)
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d7")
            assert driver.active_trip is None

    def test_batch_create_drivers(self, temp_sqlite_db):
        """Creates multiple drivers at once (100)."""
        session_maker = init_database(str(temp_sqlite_db))

        drivers = []
        for i in range(100):
            driver_dna = DriverDNA(
                acceptance_rate=0.8 + (i % 20) * 0.01,
                cancellation_tendency=0.05,
                service_quality=0.9,
                response_time=5.0,
                min_rider_rating=3.5,
                home_location=(-23.5505, -46.6333),
                preferred_zones=["zone_1"],
                shift_preference=ShiftPreference.MORNING,
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate=f"ABC-{i:04d}",
                first_name=f"Driver{i}",
                last_name="Test",
                email=f"driver{i}@email.com",
                phone=f"+551198765{i:04d}",
            )
            drivers.append((f"d{i}", driver_dna))

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.batch_create(drivers)
            session.commit()

        with session_maker() as session:
            stmt = select(Driver)
            result = session.execute(stmt)
            all_drivers = result.scalars().all()
            assert len(all_drivers) == 100

    def test_list_drivers_by_status(self, temp_sqlite_db):
        """Queries drivers by status."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(5):
            driver_dna = DriverDNA(
                acceptance_rate=0.85,
                cancellation_tendency=0.05,
                service_quality=0.92,
                response_time=5.0,
                min_rider_rating=3.5,
                home_location=(-23.5505, -46.6333),
                preferred_zones=["zone_1"],
                shift_preference=ShiftPreference.MORNING,
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate=f"TST-{i:04d}",
                first_name=f"Test{i}",
                last_name="Driver",
                email=f"test{i}@email.com",
                phone=f"+551199999{i:04d}",
            )

            with session_maker() as session:
                repo = DriverRepository(session)
                repo.create(f"d_status_{i}", driver_dna)
                if i < 3:
                    repo.update_status(f"d_status_{i}", "available")
                session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            available_drivers = repo.list_by_status("available")
            assert len(available_drivers) == 3

            offline_drivers = repo.list_by_status("offline")
            assert len(offline_drivers) == 2

    def test_list_available_drivers_in_zone(self, temp_sqlite_db):
        """Queries available drivers in zone."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(3):
            driver_dna = DriverDNA(
                acceptance_rate=0.85,
                cancellation_tendency=0.05,
                service_quality=0.92,
                response_time=5.0,
                min_rider_rating=3.5,
                home_location=(-23.5505, -46.6333),
                preferred_zones=[f"zone_{i % 2}"],
                shift_preference=ShiftPreference.MORNING,
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate=f"ZON-{i:04d}",
                first_name=f"Zone{i}",
                last_name="Driver",
                email=f"zone{i}@email.com",
                phone=f"+551188888{i:04d}",
            )

            with session_maker() as session:
                repo = DriverRepository(session)
                repo.create(f"d_zone_{i}", driver_dna)
                repo.update_status(f"d_zone_{i}", "available")
                session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            drivers = repo.list_by_status("available")
            assert len(drivers) == 3
