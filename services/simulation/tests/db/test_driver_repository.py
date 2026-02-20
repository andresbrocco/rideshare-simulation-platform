"""Tests for driver repository CRUD operations."""

import pytest
from sqlalchemy import select

from src.agents.dna import DriverDNA, ShiftPreference
from src.db.database import init_database
from src.db.repositories.driver_repository import DriverRepository
from src.db.schema import Driver
from tests.factories import DNAFactory


@pytest.mark.unit
class TestDriverRepository:
    """Test driver repository CRUD operations."""

    def test_create_driver(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Creates driver with DNA."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(
            acceptance_rate=0.85,
            home_location=(-23.5505, -46.6333),
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
            assert retrieved_dna.first_name == driver_dna.first_name

    def test_get_driver_by_id(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Retrieves driver by ID."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna()

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

    def test_update_driver_location(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates driver location only (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(acceptance_rate=0.8)

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

    def test_update_driver_status(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates driver status (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(acceptance_rate=0.88)

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

    def test_update_driver_rating(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates driver rating (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna(acceptance_rate=0.82)

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

    def test_update_active_trip(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Links driver to active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna()

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

    def test_clear_active_trip(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Clears driver active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        driver_dna = dna_factory.driver_dna()

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

    def test_batch_create_drivers(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Creates multiple drivers at once (100)."""
        session_maker = init_database(str(temp_sqlite_db))

        drivers = []
        for i in range(100):
            driver_dna = dna_factory.driver_dna(
                acceptance_rate=0.8 + (i % 20) * 0.01,
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

    def test_list_drivers_by_status(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Queries drivers by status."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(5):
            driver_dna = dna_factory.driver_dna()

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

    def test_list_available_drivers_in_zone(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Queries available drivers in zone."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(3):
            driver_dna = dna_factory.driver_dna()

            with session_maker() as session:
                repo = DriverRepository(session)
                repo.create(f"d_zone_{i}", driver_dna)
                repo.update_status(f"d_zone_{i}", "available")
                session.commit()

        with session_maker() as session:
            repo = DriverRepository(session)
            drivers = repo.list_by_status("available")
            assert len(drivers) == 3
