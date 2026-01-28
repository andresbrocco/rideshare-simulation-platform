"""Zone-based coordinate validation for DNA generation.

Provides strict point-in-polygon validation against São Paulo district zones,
replacing the previous rectangle-based bounds checking.
"""

import os
import random
from pathlib import Path

from shapely.geometry import Point, Polygon

from geo.zones import ZoneLoader

# Lazy-loaded singleton ZoneLoader
_zone_loader: ZoneLoader | None = None
_zone_polygons: dict[str, Polygon] = {}
_zones_path_override: Path | None = None


def _get_zones_path() -> Path:
    """Get the path to zones.geojson file.

    Checks in order:
    1. Path override (set via set_zones_path for testing)
    2. ZONES_GEOJSON_PATH environment variable
    3. /app/data/sao-paulo/zones.geojson (Docker)
    4. Relative to project root: data/sao-paulo/zones.geojson
    """
    # Test override
    if _zones_path_override is not None:
        return _zones_path_override

    # Environment variable override
    env_path = os.environ.get("ZONES_GEOJSON_PATH")
    if env_path:
        return Path(env_path)

    # Docker path
    docker_path = Path("/app/data/sao-paulo/zones.geojson")
    if docker_path.exists():
        return docker_path

    # Local development: find relative to this file
    # simulation/src/agents/zone_validator.py -> simulation/ -> project_root/
    project_root = Path(__file__).parent.parent.parent.parent
    local_path = project_root / "data" / "sao-paulo" / "zones.geojson"
    if local_path.exists():
        return local_path

    raise FileNotFoundError(
        "Could not find zones.geojson. Set ZONES_GEOJSON_PATH environment variable "
        "or ensure file exists at data/sao-paulo/zones.geojson"
    )


def _get_zone_loader() -> ZoneLoader:
    """Get or initialize the singleton ZoneLoader."""
    global _zone_loader, _zone_polygons

    if _zone_loader is None:
        zones_path = _get_zones_path()
        _zone_loader = ZoneLoader(zones_path)

        # Pre-build Shapely polygons for all zones
        for zone in _zone_loader.get_all_zones():
            _zone_polygons[zone.zone_id] = Polygon(zone.geometry)

    return _zone_loader


def is_location_in_any_zone(lat: float, lon: float) -> bool:
    """Check if location falls inside any of the 96 São Paulo zone polygons.

    Uses strict point-in-polygon check with no fallback to nearest zone.

    Args:
        lat: Latitude of the location
        lon: Longitude of the location

    Returns:
        True if the point is inside any zone polygon, False otherwise.
    """
    _get_zone_loader()  # Ensure polygons are loaded

    point = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)

    return any(polygon.contains(point) for polygon in _zone_polygons.values())


def get_random_location_in_zones() -> tuple[float, float]:
    """Generate a random location guaranteed to be inside a zone.

    Uses rejection sampling within a randomly selected zone's bounding box.

    Returns:
        Tuple of (lat, lon) coordinates inside a zone.

    Raises:
        RuntimeError: If unable to generate valid location after max retries.
    """
    zone_loader = _get_zone_loader()
    zones = zone_loader.get_all_zones()

    if not zones:
        raise RuntimeError("No zones loaded")

    max_retries = 100
    for _ in range(max_retries):
        # Pick a random zone
        zone = random.choice(zones)
        polygon = _zone_polygons[zone.zone_id]

        # Get bounding box (minx, miny, maxx, maxy) = (min_lon, min_lat, max_lon, max_lat)
        minx, miny, maxx, maxy = polygon.bounds

        # Generate random point within bounding box
        lon = random.uniform(minx, maxx)
        lat = random.uniform(miny, maxy)

        # Check if point is inside the polygon
        point = Point(lon, lat)
        if polygon.contains(point):
            return (lat, lon)

    raise RuntimeError(f"Failed to generate valid location after {max_retries} attempts")


def get_random_location_in_zone(zone_id: str) -> tuple[float, float]:
    """Generate a random location inside a specific zone.

    Args:
        zone_id: The zone ID to generate location within.

    Returns:
        Tuple of (lat, lon) coordinates inside the zone.

    Raises:
        ValueError: If zone_id is not found.
        RuntimeError: If unable to generate valid location after max retries.
    """
    _get_zone_loader()

    if zone_id not in _zone_polygons:
        raise ValueError(f"Zone '{zone_id}' not found")

    polygon = _zone_polygons[zone_id]
    minx, miny, maxx, maxy = polygon.bounds

    max_retries = 100
    for _ in range(max_retries):
        lon = random.uniform(minx, maxx)
        lat = random.uniform(miny, maxy)

        point = Point(lon, lat)
        if polygon.contains(point):
            return (lat, lon)

    raise RuntimeError(
        f"Failed to generate location in zone {zone_id} after {max_retries} attempts"
    )


def set_zones_path(path: Path | str | None) -> None:
    """Set or clear the zones path override. Useful for testing.

    Args:
        path: Path to zones.geojson file, or None to clear override.
    """
    global _zones_path_override
    _zones_path_override = Path(path) if path is not None else None


def reset_zone_loader() -> None:
    """Reset the singleton ZoneLoader and path override. Useful for testing."""
    global _zone_loader, _zone_polygons, _zones_path_override
    _zone_loader = None
    _zone_polygons = {}
    _zones_path_override = None
