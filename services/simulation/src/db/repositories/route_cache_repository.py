"""Route cache repository for persistent route storage."""

from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..schema import RouteCache
from ..utils import utc_now


class RouteCacheRepository:
    """Repository for persisting route cache to SQLite."""

    def __init__(self, session: Session):
        self.session = session

    def save(
        self,
        origin_h3: str,
        dest_h3: str,
        distance: float,
        duration: float,
        polyline: str | None = None,
    ) -> None:
        """Save or update a route in the cache."""
        cache_key = f"{origin_h3}|{dest_h3}"
        stmt = insert(RouteCache).values(
            cache_key=cache_key,
            origin_h3=origin_h3,
            dest_h3=dest_h3,
            distance=distance,
            duration=duration,
            polyline=polyline,
            created_at=utc_now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={
                "distance": stmt.excluded.distance,
                "duration": stmt.excluded.duration,
                "polyline": stmt.excluded.polyline,
                "created_at": stmt.excluded.created_at,
            },
        )
        self.session.execute(stmt)

    def load(self, origin_h3: str, dest_h3: str, ttl_days: int = 30) -> dict[str, Any] | None:
        """Load a route from the cache if it exists and is not expired."""
        cache_key = f"{origin_h3}|{dest_h3}"
        route = self.session.get(RouteCache, cache_key)

        if route is None:
            return None

        cutoff = utc_now() - timedelta(days=ttl_days)
        if route.created_at < cutoff:
            return None

        return {
            "distance": route.distance,
            "duration": route.duration,
            "polyline": route.polyline,
        }

    def bulk_load(self, ttl_days: int = 30) -> dict[str, dict[str, Any]]:
        """Load all non-expired routes for cache pre-population."""
        cutoff = utc_now() - timedelta(days=ttl_days)
        stmt = select(RouteCache).where(RouteCache.created_at >= cutoff)
        result = self.session.execute(stmt)

        routes = {}
        for route in result.scalars().all():
            routes[route.cache_key] = {
                "distance": route.distance,
                "duration": route.duration,
                "polyline": route.polyline,
            }
        return routes

    def bulk_save(self, routes: list[tuple[str, str, float, float, str | None]]) -> None:
        """Batch insert multiple routes."""
        if not routes:
            return

        now = utc_now()
        values = []
        for origin_h3, dest_h3, distance, duration, polyline in routes:
            values.append(
                {
                    "cache_key": f"{origin_h3}|{dest_h3}",
                    "origin_h3": origin_h3,
                    "dest_h3": dest_h3,
                    "distance": distance,
                    "duration": duration,
                    "polyline": polyline,
                    "created_at": now,
                }
            )

        stmt = insert(RouteCache).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={
                "distance": stmt.excluded.distance,
                "duration": stmt.excluded.duration,
                "polyline": stmt.excluded.polyline,
                "created_at": stmt.excluded.created_at,
            },
        )
        self.session.execute(stmt)

    def invalidate(self, origin_h3: str, dest_h3: str) -> None:
        """Delete a specific route from the cache."""
        cache_key = f"{origin_h3}|{dest_h3}"
        stmt = delete(RouteCache).where(RouteCache.cache_key == cache_key)
        self.session.execute(stmt)

    def clear_all(self) -> None:
        """Delete all routes from the cache."""
        stmt = delete(RouteCache)
        self.session.execute(stmt)

    def count(self) -> int:
        """Return total number of cached routes."""
        stmt = select(func.count()).select_from(RouteCache)
        return self.session.execute(stmt).scalar() or 0
