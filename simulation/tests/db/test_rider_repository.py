"""Tests for rider repository CRUD operations."""

import pytest
from sqlalchemy import select

from src.agents.dna import RiderDNA
from src.db.database import init_database
from src.db.repositories.rider_repository import RiderRepository
from src.db.schema import Rider


class TestRiderRepository:
    """Test rider repository CRUD operations."""

    def test_create_rider(self, temp_sqlite_db):
        """Creates rider with DNA."""
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
            assert retrieved_dna.first_name == "Maria"

    def test_get_rider_by_id(self, temp_sqlite_db):
        """Retrieves rider by ID."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.8,
            patience_threshold=200,
            max_surge_multiplier=1.8,
            avg_rides_per_week=3,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Mall", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="José",
            last_name="Lima",
            email="jose.lima@email.com",
            phone="+5511923456789",
            payment_method_type="debit_card",
            payment_method_masked="**** 5678",
        )

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

    def test_update_rider_location(self, temp_sqlite_db):
        """Updates rider location only."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.7,
            patience_threshold=150,
            max_surge_multiplier=2.5,
            avg_rides_per_week=7,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Gym", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Paula",
            last_name="Rocha",
            email="paula@email.com",
            phone="+5511934567890",
            payment_method_type="credit_card",
            payment_method_masked="**** 9012",
        )

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

    def test_update_rider_status(self, temp_sqlite_db):
        """Updates rider status."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.85,
            patience_threshold=220,
            max_surge_multiplier=1.5,
            avg_rides_per_week=4,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "School", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Fernanda",
            last_name="Dias",
            email="fernanda@email.com",
            phone="+5511945678901",
            payment_method_type="pix",
            payment_method_masked="***@bank.com",
        )

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

    def test_update_rider_rating(self, temp_sqlite_db):
        """Updates rider rating (DNA unchanged)."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.9,
            patience_threshold=240,
            max_surge_multiplier=2.2,
            avg_rides_per_week=6,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Airport", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Ricardo",
            last_name="Mendes",
            email="ricardo@email.com",
            phone="+5511956789012",
            payment_method_type="credit_card",
            payment_method_masked="**** 3456",
        )

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

    def test_update_rider_active_trip(self, temp_sqlite_db):
        """Links rider to active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.78,
            patience_threshold=190,
            max_surge_multiplier=1.9,
            avg_rides_per_week=4,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Home", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Camila",
            last_name="Souza",
            email="camila@email.com",
            phone="+5511967890123",
            payment_method_type="debit_card",
            payment_method_masked="**** 7890",
        )

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

    def test_clear_rider_active_trip(self, temp_sqlite_db):
        """Clears rider active trip."""
        session_maker = init_database(str(temp_sqlite_db))

        rider_dna = RiderDNA(
            behavior_factor=0.82,
            patience_threshold=210,
            max_surge_multiplier=2.1,
            avg_rides_per_week=5,
            frequent_destinations=[
                {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                {"name": "Home", "coordinates": (-23.5505, -46.6333)},
            ],
            home_location=(-23.5505, -46.6333),
            first_name="Thiago",
            last_name="Pereira",
            email="thiago@email.com",
            phone="+5511978901234",
            payment_method_type="pix",
            payment_method_masked="***@pix.com",
        )

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

    def test_batch_create_riders(self, temp_sqlite_db):
        """Creates multiple riders at once (50)."""
        session_maker = init_database(str(temp_sqlite_db))

        riders = []
        for i in range(50):
            rider_dna = RiderDNA(
                behavior_factor=0.7 + (i % 30) * 0.01,
                patience_threshold=180,
                max_surge_multiplier=2.0,
                avg_rides_per_week=5,
                frequent_destinations=[
                    {"name": "Work", "coordinates": (-23.5629, -46.6544)},
                    {"name": "Home", "coordinates": (-23.5505, -46.6333)},
                ],
                home_location=(-23.5505, -46.6333),
                first_name=f"Rider{i}",
                last_name="Test",
                email=f"rider{i}@email.com",
                phone=f"+551191234{i:04d}",
                payment_method_type="credit_card",
                payment_method_masked=f"**** {i:04d}",
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

    def test_list_riders_by_status(self, temp_sqlite_db):
        """Queries riders by status."""
        session_maker = init_database(str(temp_sqlite_db))

        for i in range(5):
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
                first_name=f"StatusTest{i}",
                last_name="Rider",
                email=f"statustest{i}@email.com",
                phone=f"+551198765{i:04d}",
                payment_method_type="credit_card",
                payment_method_masked=f"**** {i:04d}",
            )

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
