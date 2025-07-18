import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

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
