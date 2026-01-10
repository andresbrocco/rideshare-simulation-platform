"""Centralized geographic distance calculations.

This module provides Haversine distance calculations for determining
proximity between geographic coordinates. Used for GPS-based arrival
detection in trip execution.
"""

from math import atan2, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000  # Earth radius in meters


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
    return haversine_distance_m(lat1, lon1, lat2, lon2) <= threshold_m
