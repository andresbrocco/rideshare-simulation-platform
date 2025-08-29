import logging
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from engine import SimulationEngine

logger = logging.getLogger(__name__)


class StateSnapshotManager:
    """Manages state snapshots for client reconnection.

    Reads directly from the simulation engine's in-memory state.
    """

    def __init__(self, client: aioredis.Redis):
        self._client = client

    def _get_drivers_from_engine(self, engine: "SimulationEngine") -> list[dict]:
        """Extract driver state from engine's in-memory registry."""
        drivers = []
        for driver in engine._active_drivers.values():
            if driver.location:
                drivers.append(
                    {
                        "id": driver.driver_id,
                        "latitude": driver.location[0],
                        "longitude": driver.location[1],
                        "status": driver.status,
                        "rating": driver.current_rating,
                        "zone": getattr(driver, "_current_zone", "unknown"),
                    }
                )
        return drivers

    def _get_riders_from_engine(self, engine: "SimulationEngine") -> list[dict]:
        """Extract rider state from engine's in-memory registry."""
        riders = []
        for rider in engine._active_riders.values():
            if rider.location:
                rider_data: dict[str, Any] = {
                    "id": rider.rider_id,
                    "latitude": rider.location[0],
                    "longitude": rider.location[1],
                    "status": "waiting" if rider.status == "idle" else rider.status,
                    "rating": rider.current_rating,
                }
                # Add destination if available
                if hasattr(rider, "_destination") and rider._destination:
                    rider_data["destination_latitude"] = rider._destination[0]
                    rider_data["destination_longitude"] = rider._destination[1]
                riders.append(rider_data)
        return riders

    def _get_trips_from_engine(self, engine: "SimulationEngine") -> list[dict]:
        """Extract active trip state from engine."""
        trips = []
        # Get in-flight trips from the database
        try:
            from db.repositories.trip_repository import TripRepository

            with engine._sqlite_db() as session:
                repo = TripRepository(session)
                in_flight = repo.list_in_flight()
                for trip in in_flight:
                    trips.append(
                        {
                            "id": trip.trip_id,
                            "driver_id": trip.driver_id,
                            "rider_id": trip.rider_id,
                            "pickup_latitude": (
                                trip.pickup_location[0] if trip.pickup_location else 0
                            ),
                            "pickup_longitude": (
                                trip.pickup_location[1] if trip.pickup_location else 0
                            ),
                            "dropoff_latitude": (
                                trip.dropoff_location[0] if trip.dropoff_location else 0
                            ),
                            "dropoff_longitude": (
                                trip.dropoff_location[1] if trip.dropoff_location else 0
                            ),
                            "route": trip.route or [],
                            "status": (
                                trip.state.value
                                if hasattr(trip.state, "value")
                                else str(trip.state)
                            ),
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to get trips from engine: {e}")
        return trips

    async def get_snapshot(self, engine: "SimulationEngine | None" = None) -> dict:
        """Build snapshot from engine's in-memory state."""
        if not engine:
            return {
                "drivers": [],
                "riders": [],
                "trips": [],
                "surge": {},
                "simulation": None,
            }

        drivers = self._get_drivers_from_engine(engine)
        riders = self._get_riders_from_engine(engine)
        trips = self._get_trips_from_engine(engine)

        current_time = engine.current_time() if callable(engine.current_time) else None

        return {
            "drivers": drivers,
            "riders": riders,
            "trips": trips,
            "surge": {},
            "simulation": {
                "state": engine.state.value,
                "speed_multiplier": engine.speed_multiplier,
                "current_time": current_time.isoformat() if current_time else None,
                "drivers_count": len(drivers),
                "riders_count": len(riders),
                "active_trips_count": len(trips),
                "uptime_seconds": engine._env.now if hasattr(engine, "_env") else 0,
            },
        }
