"""Tests for trip repository CRUD operations."""

import pytest

from src.db.database import init_database
from src.db.repositories.trip_repository import TripRepository
from src.db.schema import Trip as TripModel
from src.trip import TripState


class TestTripRepository:
    """Test trip repository CRUD operations."""

    def test_create_trip(self, temp_sqlite_db):
        """Creates trip in REQUESTED state."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip1",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.2,
                fare=25.50,
            )
            session.commit()

        with session_maker() as session:
            trip = session.get(TripModel, "trip1")
            assert trip is not None
            assert trip.trip_id == "trip1"
            assert trip.rider_id == "r1"
            assert trip.state == TripState.REQUESTED.value
            assert trip.pickup_location == "-23.5505,-46.6333"
            assert trip.dropoff_location == "-23.5629,-46.6544"
            assert trip.offer_sequence == 0
            assert trip.requested_at is not None

    def test_get_trip_by_id(self, temp_sqlite_db):
        """Retrieves trip by ID."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip2",
                rider_id="r2",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip2")
            assert trip is not None
            assert trip.trip_id == "trip2"
            assert trip.state == TripState.REQUESTED
            assert trip.pickup_location == (-23.5505, -46.6333)

    def test_get_trip_not_found(self, temp_sqlite_db):
        """Returns None for missing trip."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("nonexistent")
            assert trip is None

    def test_update_trip_state_to_matched(self, temp_sqlite_db):
        """Transitions to MATCHED state."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip3",
                rider_id="r3",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=18.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip3", TripState.MATCHED, driver_id="d123")
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip3")
            assert trip.state == TripState.MATCHED
            assert trip.driver_id == "d123"
            assert trip.matched_at is not None

    def test_update_trip_state_to_started(self, temp_sqlite_db):
        """Transitions to STARTED state."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip4",
                rider_id="r4",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.5,
                fare=30.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip4", TripState.STARTED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip4")
            assert trip.state == TripState.STARTED
            assert trip.started_at is not None

    def test_update_trip_state_to_completed(self, temp_sqlite_db):
        """Transitions to COMPLETED state."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip5",
                rider_id="r5",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=22.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip5", TripState.COMPLETED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip5")
            assert trip.state == TripState.COMPLETED
            assert trip.completed_at is not None

    def test_update_trip_state_to_cancelled(self, temp_sqlite_db):
        """Transitions to CANCELLED state."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip6",
                rider_id="r6",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=15.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state(
                "trip6",
                TripState.CANCELLED,
                cancelled_by="rider",
                cancellation_reason="patience_timeout",
                cancellation_stage="requested",
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip6")
            assert trip.state == TripState.CANCELLED
            assert trip.cancelled_by == "rider"
            assert trip.cancellation_reason == "patience_timeout"
            assert trip.cancellation_stage == "requested"

    def test_increment_offer_sequence(self, temp_sqlite_db):
        """Increments offer sequence on OFFER_SENT."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip7",
                rider_id="r7",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip7", TripState.OFFER_SENT)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip7")
            assert trip.offer_sequence == 1

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip7", TripState.OFFER_EXPIRED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip7", TripState.OFFER_SENT)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip7")
            assert trip.offer_sequence == 2

    def test_list_in_flight_trips(self, temp_sqlite_db):
        """Queries trips in non-terminal states."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            # In-flight trips
            repo.create(
                trip_id="trip_requested",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_matched",
                rider_id="r2",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_started",
                rider_id="r3",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            # Terminal trips
            repo.create(
                trip_id="trip_completed",
                rider_id="r4",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_cancelled",
                rider_id="r5",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_matched", TripState.MATCHED, driver_id="d1")
            repo.update_state("trip_started", TripState.STARTED)
            repo.update_state("trip_completed", TripState.COMPLETED)
            repo.update_state(
                "trip_cancelled",
                TripState.CANCELLED,
                cancelled_by="rider",
                cancellation_reason="changed_mind",
                cancellation_stage="requested",
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            in_flight = repo.list_in_flight()
            trip_ids = [t.trip_id for t in in_flight]
            assert len(in_flight) == 3
            assert "trip_requested" in trip_ids
            assert "trip_matched" in trip_ids
            assert "trip_started" in trip_ids
            assert "trip_completed" not in trip_ids
            assert "trip_cancelled" not in trip_ids

    def test_list_trips_by_driver(self, temp_sqlite_db):
        """Queries trips by driver_id."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip_d1_1",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_d1_2",
                rider_id="r2",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=25.00,
            )
            repo.create(
                trip_id="trip_d2",
                rider_id="r3",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=30.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_d1_1", TripState.MATCHED, driver_id="d123")
            repo.update_state("trip_d1_2", TripState.MATCHED, driver_id="d123")
            repo.update_state("trip_d2", TripState.MATCHED, driver_id="d456")
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            d123_trips = repo.list_by_driver("d123")
            assert len(d123_trips) == 2
            for trip in d123_trips:
                assert trip.driver_id == "d123"

    def test_list_trips_by_rider(self, temp_sqlite_db):
        """Queries trips by rider_id."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip_r1_1",
                rider_id="r456",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_r1_2",
                rider_id="r456",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=25.00,
            )
            repo.create(
                trip_id="trip_r2",
                rider_id="r789",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=30.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            r456_trips = repo.list_by_rider("r456")
            assert len(r456_trips) == 2
            for trip in r456_trips:
                assert trip.rider_id == "r456"

    def test_list_trips_by_zone(self, temp_sqlite_db):
        """Queries trips by pickup zone."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip_z1_1",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="Z1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            repo.create(
                trip_id="trip_z1_2",
                rider_id="r2",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="Z1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=25.00,
            )
            repo.create(
                trip_id="trip_z2",
                rider_id="r3",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="Z2",
                dropoff_zone_id="zone_1",
                surge_multiplier=1.0,
                fare=30.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            z1_trips = repo.list_by_zone("Z1")
            assert len(z1_trips) == 2
            for trip in z1_trips:
                assert trip.pickup_zone_id == "Z1"

    def test_complete_trip_sets_timestamp(self, temp_sqlite_db):
        """Completing trip sets completed_at."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip_ts",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.0,
                fare=20.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_ts", TripState.COMPLETED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_ts")
            assert trip.completed_at is not None

    def test_multiple_state_transitions(self, temp_sqlite_db):
        """Tracks full trip lifecycle."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            repo.create(
                trip_id="trip_lifecycle",
                rider_id="r1",
                pickup_location=(-23.5505, -46.6333),
                dropoff_location=(-23.5629, -46.6544),
                pickup_zone_id="zone_1",
                dropoff_zone_id="zone_2",
                surge_multiplier=1.2,
                fare=28.00,
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_lifecycle")
            assert trip.requested_at is not None
            assert trip.matched_at is None
            assert trip.started_at is None
            assert trip.completed_at is None

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_lifecycle", TripState.OFFER_SENT)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_lifecycle")
            assert trip.offer_sequence == 1

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_lifecycle", TripState.MATCHED, driver_id="d1")
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_lifecycle")
            assert trip.matched_at is not None
            assert trip.driver_id == "d1"

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_lifecycle", TripState.STARTED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_lifecycle")
            assert trip.started_at is not None

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_lifecycle", TripState.COMPLETED)
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            trip = repo.get("trip_lifecycle")
            assert trip.state == TripState.COMPLETED
            assert trip.requested_at is not None
            assert trip.matched_at is not None
            assert trip.started_at is not None
            assert trip.completed_at is not None

    def test_count_in_flight(self, temp_sqlite_db):
        """Counts trips in non-terminal states."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = TripRepository(session)
            for i in range(5):
                repo.create(
                    trip_id=f"trip_count_{i}",
                    rider_id=f"r{i}",
                    pickup_location=(-23.5505, -46.6333),
                    dropoff_location=(-23.5629, -46.6544),
                    pickup_zone_id="zone_1",
                    dropoff_zone_id="zone_2",
                    surge_multiplier=1.0,
                    fare=20.00,
                )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            repo.update_state("trip_count_3", TripState.COMPLETED)
            repo.update_state(
                "trip_count_4",
                TripState.CANCELLED,
                cancelled_by="rider",
                cancellation_reason="test",
                cancellation_stage="requested",
            )
            session.commit()

        with session_maker() as session:
            repo = TripRepository(session)
            count = repo.count_in_flight()
            assert count == 3
