from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

from trip import TripState

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from engine import SimulationEngine

logger = logging.getLogger(__name__)

# Trip states that should show routes on the map
ACTIVE_TRIP_STATES = {
    TripState.REQUESTED,  # Show pending route (orange)
    TripState.OFFER_SENT,  # Show pending route (orange)
    TripState.DRIVER_ASSIGNED,  # Show pending route (orange) - brief transition state
    TripState.EN_ROUTE_PICKUP,  # Show pickup route (cyan dashed)
    TripState.AT_PICKUP,  # Show pickup route (cyan dashed)
    TripState.IN_TRANSIT,  # Show trip route (cyan solid)
}


class StateSnapshotManager:
    """Manages state snapshots for client reconnection.

    Reads directly from the simulation engine's in-memory state.
    """

    def __init__(self, client: aioredis.Redis[str]):
        self._client = client

    def _get_drivers_from_engine(self, engine: SimulationEngine) -> list[dict[str, Any]]:
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
                        "rating_count": driver.rating_count,
                        "zone": getattr(driver, "_current_zone", "unknown"),
                        "heading": getattr(driver, "_heading", 0),
                    }
                )
        return drivers

    def _get_riders_from_engine(self, engine: SimulationEngine) -> list[dict[str, Any]]:
        """Extract rider state from engine's in-memory registry."""
        # Build a map of rider_id -> trip for quick lookup
        rider_trip_map: dict[str, Any] = {}
        if hasattr(engine, "_matching_server") and hasattr(
            engine._matching_server, "get_active_trips"
        ):
            for trip in engine._matching_server.get_active_trips():
                rider_trip_map[trip.rider_id] = trip

        riders = []
        for rider in engine._active_riders.values():
            if rider.location:
                rider_data: dict[str, Any] = {
                    "id": rider.rider_id,
                    "latitude": rider.location[0],
                    "longitude": rider.location[1],
                    "status": rider.status,
                    "rating": rider.current_rating,
                    "rating_count": rider.rating_count,
                }
                # Add trip_state from active trip if available
                if rider.rider_id in rider_trip_map:
                    trip = rider_trip_map[rider.rider_id]
                    rider_data["trip_state"] = (
                        trip.state.value if hasattr(trip.state, "value") else str(trip.state)
                    )
                else:
                    rider_data["trip_state"] = "idle"
                # Add destination if available
                if hasattr(rider, "_destination") and rider._destination:
                    rider_data["destination_latitude"] = rider._destination[0]
                    rider_data["destination_longitude"] = rider._destination[1]
                riders.append(rider_data)
        return riders

    def _get_trips_from_engine(self, engine: SimulationEngine) -> list[dict[str, Any]]:
        """Extract active trip state from engine's in-memory store.

        Only includes trips in active states (EN_ROUTE_PICKUP, AT_PICKUP, IN_TRANSIT)
        to show routes on the map.
        """
        trips = []
        # Get in-memory trips from matching server (where routes are stored)
        try:
            if hasattr(engine, "_matching_server") and hasattr(
                engine._matching_server, "get_active_trips"
            ):
                all_trips = engine._matching_server.get_active_trips()
                for trip in all_trips:
                    # Only include trips in active states for route visualization
                    if trip.state in ACTIVE_TRIP_STATES:
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
                                "pickup_route": trip.pickup_route or [],
                                "route_progress_index": trip.route_progress_index,
                                "pickup_route_progress_index": trip.pickup_route_progress_index,
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

    def _get_surge_from_engine(self, engine: SimulationEngine) -> dict[str, float]:
        """Extract current surge multipliers from engine's surge calculator."""
        if hasattr(engine, "_matching_server") and engine._matching_server:
            surge_calc = getattr(engine._matching_server, "_surge_calculator", None)
            if surge_calc and hasattr(surge_calc, "current_surge"):
                return dict(surge_calc.current_surge)
        return {}

    async def get_snapshot(self, engine: SimulationEngine | None = None) -> dict[str, Any]:
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
        surge = self._get_surge_from_engine(engine)

        current_time = engine.current_time() if callable(engine.current_time) else None

        # Compute detailed driver/rider counts with single Counter pass each
        driver_counts = Counter(d.get("status") for d in drivers)
        rider_counts = Counter(r.get("status") for r in riders)

        return {
            "drivers": drivers,
            "riders": riders,
            "trips": trips,
            "surge": surge,
            "simulation": {
                "state": engine.state.value,
                "speed_multiplier": engine.speed_multiplier,
                "current_time": current_time.isoformat() if current_time else None,
                "drivers_total": len(drivers),
                "drivers_offline": driver_counts["offline"],
                "drivers_available": driver_counts["available"],
                "drivers_en_route_pickup": driver_counts["en_route_pickup"],
                "drivers_on_trip": driver_counts["on_trip"],
                "riders_total": len(riders),
                "riders_idle": rider_counts["idle"],
                "riders_requesting": rider_counts["requesting"],
                "riders_on_trip": rider_counts["on_trip"],
                "active_trips_count": len(trips),
                "uptime_seconds": engine._env.now if hasattr(engine, "_env") else 0,
            },
        }
