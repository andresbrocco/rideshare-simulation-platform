"""Standalone drive simulation for repositioning and other non-trip drives.

This module provides a pure geometry-walking function that updates a driver's
position along a route. It has no trip state, no rider mirroring, and no
route progress tracking — used for home repositioning after trip completion.
"""

from collections.abc import Generator
from typing import TYPE_CHECKING

import simpy

from agents.event_emitter import GPS_PING_INTERVAL_MOVING
from geo.distance import is_within_proximity
from geo.gps_simulation import precompute_headings

if TYPE_CHECKING:
    from agents.driver_agent import DriverAgent


def simulate_drive_along_route(
    env: simpy.Environment,
    driver: "DriverAgent",
    geometry: list[tuple[float, float]],
    duration: float,
    destination: tuple[float, float] | None = None,
    check_proximity: bool = False,
    proximity_threshold_m: float = 50.0,
) -> Generator[simpy.Event]:
    """Drive a driver along a route geometry, updating position at each GPS interval.

    This is a pure drive simulation — no trip state, no rider mirroring, no route
    progress tracking. Used for repositioning drives.

    Args:
        env: SimPy environment for timeouts
        driver: DriverAgent whose location will be updated
        geometry: List of (lat, lon) coordinates representing the route
        duration: Expected drive duration in seconds
        destination: Optional target for proximity-based early exit
        check_proximity: If True, stop when within proximity_threshold_m of destination
        proximity_threshold_m: Distance in meters for proximity detection

    Yields:
        SimPy timeout events for each GPS interval
    """
    gps_interval = GPS_PING_INTERVAL_MOVING  # 2 seconds
    num_intervals = int(duration / gps_interval)
    time_per_interval = duration / max(num_intervals, 1)
    route_headings = precompute_headings(geometry)

    for i in range(num_intervals):
        progress = (i + 1) / max(num_intervals, 1)
        idx = int(progress * (len(geometry) - 1))
        current_pos = geometry[min(idx, len(geometry) - 1)]

        route_heading = route_headings[idx] if idx < len(route_headings) else driver.heading
        driver.update_location(*current_pos, heading=route_heading)

        if (
            check_proximity
            and destination
            and is_within_proximity(
                current_pos[0],
                current_pos[1],
                destination[0],
                destination[1],
                proximity_threshold_m,
            )
        ):
            return

        yield env.timeout(time_per_interval)
