import time
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from api.auth import verify_api_key
from api.models.metrics import (
    DriverMetrics,
    OverviewMetrics,
    TripMetrics,
    ZoneMetrics,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

CACHE_TTL = 5
_metrics_cache: dict = {}


def get_engine(request: Request) -> Any:
    return request.app.state.engine


def get_driver_registry(request: Request) -> Any:
    if hasattr(request.app.state, "driver_registry"):
        return request.app.state.driver_registry
    return None


EngineDep = Annotated[Any, Depends(get_engine)]
DriverRegistryDep = Annotated[Any, Depends(get_driver_registry)]


def _get_cached_or_compute(cache_key: str, compute_func: Callable):
    now = time.time()
    if cache_key in _metrics_cache:
        entry = _metrics_cache[cache_key]
        if entry["expires_at"] > now:
            return entry["data"]

    data = compute_func()
    _metrics_cache[cache_key] = {"data": data, "expires_at": now + CACHE_TTL}
    return data


@router.get("/overview", response_model=OverviewMetrics)
def get_overview_metrics(engine: EngineDep, driver_registry: DriverRegistryDep):
    """Returns overview metrics with total counts."""

    def compute():
        total_drivers = len(engine._active_drivers) if hasattr(engine, "_active_drivers") else 0
        total_riders = len(engine._active_riders) if hasattr(engine, "_active_riders") else 0

        online_drivers = 0
        if driver_registry:
            online_drivers = driver_registry.get_all_status_counts().get("online", 0)

        waiting_riders = sum(
            1
            for rider in (
                engine._active_riders.values() if hasattr(engine, "_active_riders") else []
            )
            if hasattr(rider, "status") and rider.status == "waiting"
        )

        in_transit_riders = sum(
            1
            for rider in (
                engine._active_riders.values() if hasattr(engine, "_active_riders") else []
            )
            if hasattr(rider, "status") and rider.status == "in_trip"
        )

        active_trips = 0
        if hasattr(engine, "_get_in_flight_trips"):
            active_trips = len(engine._get_in_flight_trips())

        return OverviewMetrics(
            total_drivers=total_drivers,
            online_drivers=online_drivers,
            total_riders=total_riders,
            waiting_riders=waiting_riders,
            in_transit_riders=in_transit_riders,
            active_trips=active_trips,
            completed_trips_today=0,
        )

    return _get_cached_or_compute("overview", compute)


@router.get("/zones", response_model=list[ZoneMetrics])
def get_zone_metrics(engine: EngineDep, driver_registry: DriverRegistryDep):
    """Returns per-zone metrics with supply, demand, and surge."""

    def compute():
        zones = []
        zone_ids = ["zone_1", "zone_2", "zone_3"]

        for zone_id in zone_ids:
            online_drivers = 0
            if driver_registry:
                online_drivers = driver_registry.get_zone_driver_count(zone_id, "online")

            waiting_riders = 0
            if hasattr(engine, "_active_riders"):
                waiting_riders = sum(
                    1
                    for rider in engine._active_riders.values()
                    if hasattr(rider, "status")
                    and rider.status == "waiting"
                    and hasattr(rider, "current_zone_id")
                    and rider.current_zone_id == zone_id
                )

            zones.append(
                ZoneMetrics(
                    zone_id=zone_id,
                    zone_name=zone_id.replace("_", " ").title(),
                    online_drivers=online_drivers,
                    waiting_riders=waiting_riders,
                    active_trips=0,
                    surge_multiplier=1.0,
                )
            )

        return zones

    return _get_cached_or_compute("zones", compute)


@router.get("/trips", response_model=TripMetrics)
def get_trip_metrics(engine: EngineDep):
    """Returns trip statistics including active, completed, and averages."""

    def compute():
        active_trips = 0
        if hasattr(engine, "_get_in_flight_trips"):
            active_trips = len(engine._get_in_flight_trips())

        return TripMetrics(
            active_trips=active_trips,
            completed_today=0,
            cancelled_today=0,
            avg_fare=0.0,
            avg_duration_minutes=0.0,
        )

    return _get_cached_or_compute("trips", compute)


@router.get("/drivers", response_model=DriverMetrics)
def get_driver_metrics(driver_registry: DriverRegistryDep):
    """Returns driver status counts."""

    def compute():
        if not driver_registry:
            return DriverMetrics(
                online=0,
                offline=0,
                busy=0,
                en_route_pickup=0,
                en_route_destination=0,
                total=0,
            )

        status_counts = driver_registry.get_all_status_counts()
        online = status_counts.get("online", 0)
        offline = status_counts.get("offline", 0)
        busy = status_counts.get("busy", 0)
        en_route_pickup = status_counts.get("en_route_pickup", 0)
        en_route_destination = status_counts.get("en_route_destination", 0)
        total = online + offline + busy + en_route_pickup + en_route_destination

        return DriverMetrics(
            online=online,
            offline=offline,
            busy=busy,
            en_route_pickup=en_route_pickup,
            en_route_destination=en_route_destination,
            total=total,
        )

    return _get_cached_or_compute("drivers", compute)
