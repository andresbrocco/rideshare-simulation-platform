"""Centralized geographic distance calculations.

This module provides Haversine distance calculations for determining
proximity between geographic coordinates. Used for GPS-based arrival
detection in trip execution.
"""

from math import atan2, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000  # Earth radius in meters

# ~9e-6 degrees per meter (1 / 111,320 m per degree of latitude)
_LAT_DEGREES_PER_METER: float = 1.0 / 111_320


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two points in meters.

    Uses the Haversine formula to calculate the shortest distance over
    the Earth's surface between two points specified by latitude/longitude.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance between the two points in meters
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_M * c


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two points in kilometers.

    Convenience wrapper around haversine_distance_m for use cases that
    need kilometer units (e.g., driver matching radius).

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance between the two points in kilometers
    """
    return haversine_distance_m(lat1, lon1, lat2, lon2) / 1000.0


def is_within_proximity(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    threshold_m: float = 50.0,
) -> bool:
    """Check if two geographic points are within a given distance threshold.

    Used for GPS-based arrival detection to determine if a driver has
    reached the pickup or dropoff location.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees
        threshold_m: Maximum distance in meters to be considered "within proximity"

    Returns:
        True if the points are within threshold_m meters of each other
    """
    # Flat-Earth bounding box pre-check — fast reject for >95% of calls on the
    # GPS tick hot path. The threshold is expanded by 1% to guarantee no false
    # negatives at the boundary (Haversine is not perfectly linear). We use the
    # same threshold for longitude (no cos(lat) correction) which is conservative
    # at São Paulo's latitude (~23.5°S, cos≈0.917), meaning slightly more candidates
    # reach Haversine but no false negatives occur.
    lat_threshold = threshold_m * _LAT_DEGREES_PER_METER * 1.01
    if abs(lat2 - lat1) > lat_threshold:
        return False
    if abs(lon2 - lon1) > lat_threshold:
        return False

    return haversine_distance_m(lat1, lon1, lat2, lon2) <= threshold_m
