import json
import logging
import math
from pathlib import Path

from pydantic import BaseModel, Field
from shapely.geometry import Point, Polygon

logger = logging.getLogger(__name__)


class Zone(BaseModel):
    zone_id: str
    name: str
    demand_multiplier: float = Field(default=1.0, gt=0.0)
    surge_sensitivity: float = Field(default=1.0, ge=0.0, le=2.0)
    geometry: list[tuple[float, float]]
    centroid: tuple[float, float]


class ZoneLoader:
    def __init__(self, geojson_path: Path | str):
        self.geojson_path = Path(geojson_path)
        self._zones: dict[str, Zone] = {}
        self._load_zones()

    def _load_zones(self) -> None:
        with open(self.geojson_path) as f:
            geojson = json.load(f)

        if geojson.get("type") != "FeatureCollection":
            logger.warning(f"Expected FeatureCollection, got {geojson.get('type')}")
            return

        features = geojson.get("features", [])
        for feature in features:
            zone = self._parse_feature(feature)
            if zone:
                self._zones[zone.zone_id] = zone

        logger.info(f"Loaded {len(self._zones)} zones from {self.geojson_path}")

    @staticmethod
    def _parse_feature(feature: dict) -> Zone | None:
        try:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})

            zone_id = properties.get("zone_id")
            if not zone_id:
                logger.warning("Skipping feature with missing zone_id")
                return None

            if geometry.get("type") != "Polygon":
                logger.warning(
                    f"Skipping zone {zone_id}: unsupported geometry type {geometry.get('type')}"
                )
                return None

            coordinates = geometry.get("coordinates", [[]])
            if not coordinates or not coordinates[0]:
                logger.warning(f"Skipping zone {zone_id}: empty coordinates")
                return None

            outer_ring = coordinates[0]
            polygon_coords = [(lon, lat) for lon, lat in outer_ring]

            centroid = ZoneLoader._calculate_centroid(polygon_coords)

            zone = Zone(
                zone_id=zone_id,
                name=properties.get("name", zone_id),
                demand_multiplier=properties.get("demand_multiplier", 1.0),
                surge_sensitivity=properties.get("surge_sensitivity", 1.0),
                geometry=polygon_coords,
                centroid=centroid,
            )

            return zone

        except Exception as e:
            logger.warning(f"Error parsing feature: {e}")
            return None

    @staticmethod
    def _calculate_centroid(polygon_coords: list[tuple[float, float]]) -> tuple[float, float]:
        if not polygon_coords:
            raise ValueError("Cannot calculate centroid of empty polygon")

        lon_sum = sum(coord[0] for coord in polygon_coords)
        lat_sum = sum(coord[1] for coord in polygon_coords)
        count = len(polygon_coords)

        return (lon_sum / count, lat_sum / count)

    def get_zone(self, zone_id: str) -> Zone | None:
        return self._zones.get(zone_id)

    def get_all_zones(self) -> list[Zone]:
        return list(self._zones.values())

    def find_zone_for_location(self, lat: float, lon: float) -> str | None:
        """Find the zone containing the given location using point-in-polygon test.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            Zone ID if found, otherwise falls back to nearest centroid.
            Returns None if no zones are loaded.
        """
        if not self._zones:
            return None

        point = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)

        # First try exact point-in-polygon match
        for zone in self._zones.values():
            polygon = Polygon(zone.geometry)
            if polygon.contains(point):
                return zone.zone_id

        # Fallback: find nearest centroid
        return self._find_nearest_zone_by_centroid(lat, lon)

    def _find_nearest_zone_by_centroid(self, lat: float, lon: float) -> str | None:
        """Find zone with nearest centroid to the given location."""
        if not self._zones:
            return None

        nearest_zone_id = None
        min_distance = float("inf")

        for zone in self._zones.values():
            centroid_lon, centroid_lat = zone.centroid
            distance = self._haversine_distance(lat, lon, centroid_lat, centroid_lon)
            if distance < min_distance:
                min_distance = distance
                nearest_zone_id = zone.zone_id

        return nearest_zone_id

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers using Haversine formula."""
        R = 6371  # Earth radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c
