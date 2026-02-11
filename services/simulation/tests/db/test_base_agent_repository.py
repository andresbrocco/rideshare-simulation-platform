"""Tests for base agent repository generic functionality."""

import pytest
from sqlalchemy import select

from src.agents.dna import DriverDNA, RiderDNA
from src.db.database import init_database
from src.db.repositories.driver_repository import DriverRepository
from src.db.repositories.rider_repository import RiderRepository
from src.db.schema import Driver, Rider
from tests.factories import DNAFactory


@pytest.mark.unit
class TestBaseAgentRepositoryGenericBehavior:
    """Test that both repositories share identical behavior through base class."""

    def test_driver_repo_inherits_from_base(self):
        """DriverRepository inherits from BaseAgentRepository."""
        from src.db.repositories.base_agent_repository import BaseAgentRepository

        assert issubclass(DriverRepository, BaseAgentRepository)

    def test_rider_repo_inherits_from_base(self):
        """RiderRepository inherits from BaseAgentRepository."""
        from src.db.repositories.base_agent_repository import BaseAgentRepository

        assert issubclass(RiderRepository, BaseAgentRepository)

    def test_driver_repo_has_model_class(self):
        """DriverRepository specifies Driver as model_class."""
        assert DriverRepository.model_class is Driver

    def test_rider_repo_has_model_class(self):
        """RiderRepository specifies Rider as model_class."""
        assert RiderRepository.model_class is Rider


@pytest.mark.unit
class TestBaseAgentRepositoryPolymorphism:
    """Test that both repos work interchangeably through base class interface."""

    def test_create_driver_through_base_interface(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Can create driver using generic interface."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna(home_location=(-23.55, -46.63))

        with session_maker() as session:
            repo = DriverRepository(session)
            repo.create("d_base_1", driver_dna)
            session.commit()

        with session_maker() as session:
            driver = session.get(Driver, "d_base_1")
            assert driver is not None
            assert driver.status == "offline"

    def test_create_rider_through_base_interface(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Can create rider using generic interface."""
        session_maker = init_database(str(temp_sqlite_db))
        rider_dna = dna_factory.rider_dna(home_location=(-23.55, -46.63))

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r_base_1", rider_dna)
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r_base_1")
            assert rider is not None
            assert rider.status == "offline"

    def test_get_returns_correct_model_type(self, temp_sqlite_db, dna_factory: DNAFactory):
        """get() returns the correct ORM model type for each repository."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            DriverRepository(session).create("d_type_1", driver_dna)
            RiderRepository(session).create("r_type_1", rider_dna)
            session.commit()

        with session_maker() as session:
            driver = DriverRepository(session).get("d_type_1")
            rider = RiderRepository(session).get("r_type_1")

            assert isinstance(driver, Driver)
            assert isinstance(rider, Rider)

    def test_list_by_status_returns_correct_model_type(
        self, temp_sqlite_db, dna_factory: DNAFactory
    ):
        """list_by_status returns correct model types."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            driver_repo = DriverRepository(session)
            rider_repo = RiderRepository(session)

            driver_repo.create("d_ls_1", driver_dna)
            driver_repo.update_status("d_ls_1", "available")

            rider_repo.create("r_ls_1", rider_dna)
            rider_repo.update_status("r_ls_1", "waiting")

            session.commit()

        with session_maker() as session:
            drivers = DriverRepository(session).list_by_status("available")
            riders = RiderRepository(session).list_by_status("waiting")

            assert len(drivers) == 1
            assert len(riders) == 1
            assert all(isinstance(d, Driver) for d in drivers)
            assert all(isinstance(r, Rider) for r in riders)


@pytest.mark.unit
class TestBaseAgentRepositoryTypeIsolation:
    """Test that driver and rider data remain isolated."""

    def test_driver_repo_does_not_see_riders(self, temp_sqlite_db, dna_factory: DNAFactory):
        """DriverRepository only sees drivers, not riders."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            DriverRepository(session).create("d_iso_1", driver_dna)
            RiderRepository(session).create("r_iso_1", rider_dna)
            session.commit()

        with session_maker() as session:
            driver_repo = DriverRepository(session)
            # Driver repo should not be able to get rider
            result = driver_repo.get("r_iso_1")
            assert result is None

    def test_rider_repo_does_not_see_drivers(self, temp_sqlite_db, dna_factory: DNAFactory):
        """RiderRepository only sees riders, not drivers."""
        session_maker = init_database(str(temp_sqlite_db))
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            DriverRepository(session).create("d_iso_2", driver_dna)
            RiderRepository(session).create("r_iso_2", rider_dna)
            session.commit()

        with session_maker() as session:
            rider_repo = RiderRepository(session)
            # Rider repo should not be able to get driver
            result = rider_repo.get("d_iso_2")
            assert result is None


@pytest.mark.unit
class TestBaseAgentRepositoryExport:
    """Test that BaseAgentRepository is properly exported."""

    def test_base_class_exported_from_package(self):
        """BaseAgentRepository is exported from repositories package."""
        from src.db.repositories import BaseAgentRepository

        assert BaseAgentRepository is not None

    def test_all_repositories_exported(self):
        """All repositories remain exported after refactoring."""
        from src.db.repositories import (
            BaseAgentRepository,
            DriverRepository,
            RiderRepository,
        )

        assert BaseAgentRepository is not None
        assert DriverRepository is not None
        assert RiderRepository is not None
