"""Tests for route cache repository persistence."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.db.database import init_database
from src.db.repositories.route_cache_repository import RouteCacheRepository
from src.db.schema import RouteCache
from src.db.utils import utc_now


@pytest.mark.unit
class TestRouteCacheRepository:
    """Test route cache repository operations."""

    def test_create_route_cache_table(self, temp_sqlite_db):
        """Creates route_cache table with correct columns."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            # Table should exist after init
            result = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='route_cache'")
            ).fetchone()
            assert result is not None

            # Check columns exist
            columns_result = session.execute(text("PRAGMA table_info(route_cache)")).fetchall()
            column_names = [col[1] for col in columns_result]
            expected = [
                "cache_key",
                "origin_h3",
                "dest_h3",
                "distance",
                "duration",
                "polyline",
                "created_at",
            ]
            for col in expected:
                assert col in column_names

    def test_save_route(self, temp_sqlite_db):
        """Persists route to database."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="89754e64993ffff",
                dest_h3="89754e64997ffff",
                distance=5432.1,
                duration=720.5,
                polyline="encoded_polyline_string",
            )
            session.commit()

        with session_maker() as session:
            route = session.get(RouteCache, "89754e64993ffff|89754e64997ffff")
            assert route is not None
            assert route.origin_h3 == "89754e64993ffff"
            assert route.dest_h3 == "89754e64997ffff"
            assert route.distance == 5432.1
            assert route.duration == 720.5
            assert route.polyline == "encoded_polyline_string"
            assert route.created_at is not None

    def test_load_route(self, temp_sqlite_db):
        """Loads route from database."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="89754e64993ffff",
                dest_h3="89754e64997ffff",
                distance=5432.1,
                duration=720.5,
                polyline="test_polyline",
            )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.load("89754e64993ffff", "89754e64997ffff")

            assert result is not None
            assert result["distance"] == 5432.1
            assert result["duration"] == 720.5
            assert result["polyline"] == "test_polyline"

    def test_load_route_not_found(self, temp_sqlite_db):
        """Returns None for missing route."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.load("nonexistent_origin", "nonexistent_dest")
            assert result is None

    def test_bulk_load_all_routes(self, temp_sqlite_db):
        """Loads all routes on startup."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            for i in range(100):
                repo.save(
                    origin_h3=f"origin_{i:03d}",
                    dest_h3=f"dest_{i:03d}",
                    distance=float(i * 100),
                    duration=float(i * 10),
                )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.bulk_load(ttl_days=30)

            assert len(result) == 100
            assert "origin_000|dest_000" in result
            assert "origin_099|dest_099" in result
            assert result["origin_050|dest_050"]["distance"] == 5000.0

    def test_route_ttl_expiration(self, temp_sqlite_db):
        """Filters expired routes on load."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            # Fresh route
            repo.save(
                origin_h3="fresh_origin",
                dest_h3="fresh_dest",
                distance=1000.0,
                duration=100.0,
            )
            session.commit()

            # Manually backdate a route to 40 days ago (naive datetime for SQLite)
            expired_route = RouteCache(
                cache_key="expired_origin|expired_dest",
                origin_h3="expired_origin",
                dest_h3="expired_dest",
                distance=2000.0,
                duration=200.0,
                created_at=utc_now() - timedelta(days=40),
            )
            session.add(expired_route)
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.bulk_load(ttl_days=30)

            assert "fresh_origin|fresh_dest" in result
            assert "expired_origin|expired_dest" not in result

    def test_cache_invalidation_by_key(self, temp_sqlite_db):
        """Deletes specific cached route."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="to_delete_origin",
                dest_h3="to_delete_dest",
                distance=1000.0,
                duration=100.0,
            )
            repo.save(
                origin_h3="keep_origin",
                dest_h3="keep_dest",
                distance=2000.0,
                duration=200.0,
            )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.invalidate("to_delete_origin", "to_delete_dest")
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            deleted = repo.load("to_delete_origin", "to_delete_dest")
            kept = repo.load("keep_origin", "keep_dest")

            assert deleted is None
            assert kept is not None

    def test_cache_invalidation_all(self, temp_sqlite_db):
        """Clears entire cache."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            for i in range(10):
                repo.save(
                    origin_h3=f"origin_{i}",
                    dest_h3=f"dest_{i}",
                    distance=float(i * 100),
                    duration=float(i * 10),
                )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            assert repo.count() == 10
            repo.clear_all()
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            assert repo.count() == 0

    def test_bulk_save_routes(self, temp_sqlite_db):
        """Saves multiple routes efficiently."""
        session_maker = init_database(str(temp_sqlite_db))

        routes = [
            (f"bulk_origin_{i}", f"bulk_dest_{i}", float(i * 100), float(i * 10), None)
            for i in range(50)
        ]

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.bulk_save(routes)
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            assert repo.count() == 50

            result = repo.bulk_load()
            assert "bulk_origin_0|bulk_dest_0" in result
            assert "bulk_origin_49|bulk_dest_49" in result

    def test_cache_key_format(self, temp_sqlite_db):
        """Uses consistent key format."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="89754e64993ffff",
                dest_h3="89754e64997ffff",
                distance=1000.0,
                duration=100.0,
            )
            session.commit()

        with session_maker() as session:
            route = session.get(RouteCache, "89754e64993ffff|89754e64997ffff")
            assert route is not None
            assert route.cache_key == "89754e64993ffff|89754e64997ffff"

    def test_route_without_polyline(self, temp_sqlite_db):
        """Handles routes without geometry."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="no_poly_origin",
                dest_h3="no_poly_dest",
                distance=3000.0,
                duration=300.0,
            )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.load("no_poly_origin", "no_poly_dest")

            assert result is not None
            assert result["distance"] == 3000.0
            assert result["polyline"] is None

    def test_upsert_overwrites_existing(self, temp_sqlite_db):
        """Saving with same key updates existing route."""
        session_maker = init_database(str(temp_sqlite_db))

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="update_origin",
                dest_h3="update_dest",
                distance=1000.0,
                duration=100.0,
            )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            repo.save(
                origin_h3="update_origin",
                dest_h3="update_dest",
                distance=2000.0,
                duration=200.0,
                polyline="new_polyline",
            )
            session.commit()

        with session_maker() as session:
            repo = RouteCacheRepository(session)
            result = repo.load("update_origin", "update_dest")
            assert repo.count() == 1
            assert result["distance"] == 2000.0
            assert result["duration"] == 200.0
            assert result["polyline"] == "new_polyline"
