import math

from shapely.geometry import Point, Polygon

from .zones import ZoneLoader


class InvalidCoordinatesError(Exception):
    """Raised when coordinates are too far from all zone centroids"""

    pass


class ZoneAssignmentService:
    """Assigns geographic coordinates to zones using point-in-polygon and nearest centroid fallback"""

    def __init__(self, zone_loader: ZoneLoader):
        self.zone_loader = zone_loader
        self._cache: dict[str, str] = {}
        self._polygons: dict[str, Polygon] = {}
        self._build_polygons()

    def _build_polygons(self) -> None:
        """Pre-build Shapely polygons for all zones"""
        for zone in self.zone_loader.get_all_zones():
            # Zone.geometry stores (lon, lat) tuples
            self._polygons[zone.zone_id] = Polygon(zone.geometry)

    def get_zone_id(self, lat: float, lon: float) -> str:
        """Get zone ID for given coordinates"""
        cache_key = f"{lat:.6f},{lon:.6f}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        zone_id = self._find_zone(lat, lon)
        self._cache[cache_key] = zone_id
        return zone_id

    def _find_zone(self, lat: float, lon: float) -> str:
        """Find zone using point-in-polygon, fallback to nearest centroid"""
        # Create Shapely Point (lon, lat order!)
        point = Point(lon, lat)

        # Check if point is inside any polygon
        for zone_id, polygon in self._polygons.items():
            if polygon.contains(point):
                return zone_id

        # Fallback: find nearest centroid within 50km
        return self._find_nearest_zone(lat, lon)

    def _find_nearest_zone(self, lat: float, lon: float) -> str:
        """Find nearest zone by centroid distance"""
        min_distance = float("inf")
        nearest_zone_id: str | None = None

        for zone in self.zone_loader.get_all_zones():
            # Zone.centroid is (lon, lat)
            centroid_lon, centroid_lat = zone.centroid
            distance = self._calculate_distance(lat, lon, centroid_lat, centroid_lon)

            if distance < min_distance:
                min_distance = distance
                nearest_zone_id = zone.zone_id

        if nearest_zone_id is None or min_distance > 50.0:
            raise InvalidCoordinatesError(
                f"Coordinates ({lat}, {lon}) are {min_distance:.2f}km from nearest zone (max 50km)"
            )

        return nearest_zone_id

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance in kilometers"""
        R = 6371.0  # Earth radius in km

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def get_zone_batch(self, coords: list[tuple[float, float]]) -> list[str]:
        """Assign zones for multiple coordinates"""
        return [self.get_zone_id(lat, lon) for lat, lon in coords]
