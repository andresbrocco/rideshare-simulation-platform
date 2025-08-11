import math

import h3


class DriverGeospatialIndex:
    """Spatial index for driver locations using H3 hexagonal cells."""

    def __init__(self, h3_resolution: int = 9):
        self._h3_resolution = h3_resolution
        self._h3_cells: dict[str, set[str]] = {}
        self._driver_locations: dict[str, tuple[float, float]] = {}
        self._driver_status: dict[str, str] = {}

    def add_driver(self, driver_id: str, lat: float, lon: float, status: str) -> None:
        cell = self._get_h3_cell(lat, lon)
        if cell not in self._h3_cells:
            self._h3_cells[cell] = set()
        self._h3_cells[cell].add(driver_id)
        self._driver_locations[driver_id] = (lat, lon)
        self._driver_status[driver_id] = status

    def update_driver_location(self, driver_id: str, lat: float, lon: float) -> None:
        if driver_id not in self._driver_locations:
            return

        old_lat, old_lon = self._driver_locations[driver_id]
        old_cell = self._get_h3_cell(old_lat, old_lon)
        new_cell = self._get_h3_cell(lat, lon)

        if old_cell != new_cell:
            if old_cell in self._h3_cells:
                self._h3_cells[old_cell].discard(driver_id)
                if not self._h3_cells[old_cell]:
                    del self._h3_cells[old_cell]

            if new_cell not in self._h3_cells:
                self._h3_cells[new_cell] = set()
            self._h3_cells[new_cell].add(driver_id)

        self._driver_locations[driver_id] = (lat, lon)

    def update_driver_status(self, driver_id: str, status: str) -> None:
        if driver_id in self._driver_status:
            self._driver_status[driver_id] = status

    def remove_driver(self, driver_id: str) -> None:
        if driver_id not in self._driver_locations:
            return

        lat, lon = self._driver_locations[driver_id]
        cell = self._get_h3_cell(lat, lon)

        if cell in self._h3_cells:
            self._h3_cells[cell].discard(driver_id)
            if not self._h3_cells[cell]:
                del self._h3_cells[cell]

        del self._driver_locations[driver_id]
        del self._driver_status[driver_id]

    def find_nearest_drivers(
        self, lat: float, lon: float, radius_km: float = 5.0, status_filter: str = "online"
    ) -> list[tuple[str, float]]:
        if not self._driver_locations:
            return []

        center_cell = self._get_h3_cell(lat, lon)
        # k rings for coverage - resolution 9 has ~174m edge length
        k = max(1, int(radius_km * 1000 / 174) + 1)
        cells_to_check = h3.grid_disk(center_cell, k)

        candidates = []
        for cell in cells_to_check:
            if cell in self._h3_cells:
                for driver_id in self._h3_cells[cell]:
                    if self._driver_status.get(driver_id) == status_filter:
                        driver_lat, driver_lon = self._driver_locations[driver_id]
                        distance = self._haversine_distance(lat, lon, driver_lat, driver_lon)
                        if distance <= radius_km:
                            candidates.append((driver_id, distance))

        candidates.sort(key=lambda x: x[1])
        return candidates

    def _get_h3_cell(self, lat: float, lon: float) -> str:
        return h3.latlng_to_cell(lat, lon, self._h3_resolution)

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
