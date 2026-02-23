import threading

import h3

from geo.distance import haversine_distance_km


class DriverGeospatialIndex:
    """Spatial index for driver locations using H3 hexagonal cells."""

    def __init__(self, h3_resolution: int = 9):
        self._h3_resolution = h3_resolution
        self._h3_cells: dict[str, set[str]] = {}
        self._driver_locations: dict[str, tuple[float, float, str]] = {}
        self._driver_status: dict[str, str] = {}
        self._lock = threading.Lock()  # Thread safety for concurrent access

    def add_driver(self, driver_id: str, lat: float, lon: float, status: str) -> None:
        with self._lock:
            cell = self._get_h3_cell(lat, lon)
            if cell not in self._h3_cells:
                self._h3_cells[cell] = set()
            self._h3_cells[cell].add(driver_id)
            self._driver_locations[driver_id] = (lat, lon, cell)
            self._driver_status[driver_id] = status

    def update_driver_location(self, driver_id: str, lat: float, lon: float) -> None:
        with self._lock:
            if driver_id not in self._driver_locations:
                return

            _, _, old_cell = self._driver_locations[driver_id]
            new_cell = self._get_h3_cell(lat, lon)

            if old_cell != new_cell:
                if old_cell in self._h3_cells:
                    self._h3_cells[old_cell].discard(driver_id)
                    if not self._h3_cells[old_cell]:
                        del self._h3_cells[old_cell]

                if new_cell not in self._h3_cells:
                    self._h3_cells[new_cell] = set()
                self._h3_cells[new_cell].add(driver_id)

            self._driver_locations[driver_id] = (lat, lon, new_cell)

    def update_driver_status(self, driver_id: str, status: str) -> None:
        with self._lock:
            if driver_id in self._driver_status:
                self._driver_status[driver_id] = status

    def remove_driver(self, driver_id: str) -> None:
        with self._lock:
            if driver_id not in self._driver_locations:
                return

            _, _, cell = self._driver_locations[driver_id]

            if cell in self._h3_cells:
                self._h3_cells[cell].discard(driver_id)
                if not self._h3_cells[cell]:
                    del self._h3_cells[cell]

            del self._driver_locations[driver_id]
            del self._driver_status[driver_id]

    def find_nearest_drivers(
        self,
        lat: float,
        lon: float,
        radius_km: float = 5.0,
        status_filter: str | set[str] = "available",
    ) -> list[tuple[str, float]]:
        with self._lock:
            if not self._driver_locations:
                return []

            # Normalize status_filter to a set for uniform comparison
            filter_set: set[str] = (
                {status_filter} if isinstance(status_filter, str) else status_filter
            )

            center_cell = self._get_h3_cell(lat, lon)
            # Maximum k rings for full radius coverage at resolution 9 (~174m edge)
            _max_k = max(1, int(radius_km * 1000 / 174) + 1)

            candidates: list[tuple[str, float]] = []
            checked_cells: set[str] = set()

            # Progressive ring expansion: start small, double outward only if needed
            k = 5
            while True:
                current_k = min(k, _max_k)
                ring_cells = set(h3.grid_disk(center_cell, current_k))
                new_cells = ring_cells - checked_cells
                checked_cells |= ring_cells

                for cell in new_cells:
                    if cell in self._h3_cells:
                        for driver_id in self._h3_cells[cell]:
                            if self._driver_status.get(driver_id) in filter_set:
                                driver_lat, driver_lon, _ = self._driver_locations[driver_id]
                                distance = haversine_distance_km(lat, lon, driver_lat, driver_lon)
                                if distance <= radius_km:
                                    candidates.append((driver_id, distance))

                # Stop if we've reached the max search radius or found candidates
                if current_k >= _max_k or candidates:
                    break

                k = k * 2

            candidates.sort(key=lambda x: x[1])
            return candidates

    def _get_h3_cell(self, lat: float, lon: float) -> str:
        return h3.latlng_to_cell(lat, lon, self._h3_resolution)

    def clear(self) -> None:
        """Clear all index state for simulation reset."""
        with self._lock:
            self._h3_cells.clear()
            self._driver_locations.clear()
            self._driver_status.clear()
