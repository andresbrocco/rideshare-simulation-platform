"""Tests for rider repository CRUD operations."""

import pytest
from sqlalchemy import select

from src.agents.dna import RiderDNA
from src.db.database import init_database
from src.db.repositories.rider_repository import RiderRepository
from src.db.schema import Rider
from tests.factories import DNAFactory


class TestRiderRepository:
    """Test rider repository CRUD operations."""

    def test_create_rider(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Creates rider with DNA."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(
            behavior_factor=0.75,
            home_location=(-23.5505, -46.6333),
        )

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r1", rider_dna)
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r1")
            assert rider is not None
            assert rider.id == "r1"
            assert rider.status == "idle"
            assert rider.current_location == "-23.5505,-46.6333"

            retrieved_dna = RiderDNA.model_validate_json(rider.dna_json)
            assert retrieved_dna.behavior_factor == 0.75
            assert retrieved_dna.first_name == rider_dna.first_name

    def test_get_rider_by_id(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Retrieves rider by ID."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r2", rider_dna)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            rider = repo.get("r2")
            assert rider is not None
            assert rider.id == "r2"

    def test_get_rider_not_found(self, temp_sqlite_db):
        """Returns None for missing rider."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RiderRepository(session)
            rider = repo.get("nonexistent")
            assert rider is None

    def test_update_rider_location(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates rider location only."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(behavior_factor=0.7)

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r3", rider_dna)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.update_location("r3", (-23.5629, -46.6544))
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r3")
            assert rider.current_location == "-23.5629,-46.6544"

            retrieved_dna = RiderDNA.model_validate_json(rider.dna_json)
            assert retrieved_dna.behavior_factor == 0.7

    def test_update_rider_status(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates rider status."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(behavior_factor=0.85)

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r4", rider_dna)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.update_status("r4", "waiting")
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r4")
            assert rider.status == "waiting"

            retrieved_dna = RiderDNA.model_validate_json(rider.dna_json)
            assert retrieved_dna.behavior_factor == 0.85

    def test_update_rider_rating(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Updates rider rating (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna(behavior_factor=0.9)

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r5", rider_dna)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.update_rating("r5", 4.7, 15)
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r5")
            assert rider.current_rating == 4.7
            assert rider.rating_count == 15

            retrieved_dna = RiderDNA.model_validate_json(rider.dna_json)
            assert retrieved_dna.behavior_factor == 0.9

    def test_update_rider_active_trip(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Links rider to active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r6", rider_dna)
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.update_active_trip("r6", "trip789")
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r6")
            assert rider.active_trip == "trip789"

    def test_clear_rider_active_trip(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Clears rider active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = dna_factory.rider_dna()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.create("r7", rider_dna)
            repo.update_active_trip("r7", "trip999")
            session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.update_active_trip("r7", None)
            session.commit()

        with session_maker() as session:
            rider = session.get(Rider, "r7")
            assert rider.active_trip is None

    def test_batch_create_riders(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Creates multiple riders at once (50)."""
        session_maker = init_database(str(temp_sqlite_db))

        riders = []
        for i in range(50):
            rider_dna = dna_factory.rider_dna(
                behavior_factor=0.7 + (i % 30) * 0.01,
            )
            riders.append((f"r{i}", rider_dna))

        with session_maker() as session:
            repo = RiderRepository(session)
            repo.batch_create(riders)
            session.commit()

        with session_maker() as session:
            stmt = select(Rider)
            result = session.execute(stmt)
            all_riders = result.scalars().all()
            assert len(all_riders) == 50

    def test_list_riders_by_status(self, temp_sqlite_db, dna_factory: DNAFactory):
        """Queries riders by status."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(5):
            rider_dna = dna_factory.rider_dna()

            with session_maker() as session:
                repo = RiderRepository(session)
                repo.create(f"r_status_{i}", rider_dna)
                if i < 2:
                    repo.update_status(f"r_status_{i}", "waiting")
                session.commit()

        with session_maker() as session:
            repo = RiderRepository(session)
            waiting_riders = repo.list_by_status("waiting")
            assert len(waiting_riders) == 2

            idle_riders = repo.list_by_status("idle")
            assert len(idle_riders) == 3
