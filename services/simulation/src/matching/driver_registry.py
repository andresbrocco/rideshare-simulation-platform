import threading
from dataclasses import dataclass


@dataclass
class DriverRecord:
    driver_id: str
    status: str
    zone_id: str | None = None
    location: tuple[float, float] | None = None


class DriverRegistry:
    """Registry for tracking driver status and zone membership.

    Thread-safe: All methods are protected by a lock for concurrent access
    from the SimPy background thread and FastAPI main thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._drivers: dict[str, DriverRecord] = {}
        self._status_counts: dict[str, int] = {
            "available": 0,
            "offline": 0,
            "en_route_pickup": 0,
            "on_trip": 0,
        }
        self._zone_status_counts: dict[str, dict[str, int]] = {}

    def register_driver(
        self,
        driver_id: str,
        status: str,
        zone_id: str | None = None,
        location: tuple[float, float] | None = None,
    ) -> None:
        with self._lock:
            record = DriverRecord(
                driver_id=driver_id, status=status, zone_id=zone_id, location=location
            )
            self._drivers[driver_id] = record
            self._status_counts[status] += 1

            if zone_id:
                if zone_id not in self._zone_status_counts:
                    self._zone_status_counts[zone_id] = {
                        "available": 0,
                        "offline": 0,
                        "en_route_pickup": 0,
                        "on_trip": 0,
                    }
                self._zone_status_counts[zone_id][status] += 1

    def update_driver_status(self, driver_id: str, new_status: str) -> None:
        with self._lock:
            if driver_id not in self._drivers:
                return

            record = self._drivers[driver_id]
            old_status = record.status

            self._status_counts[old_status] -= 1
            self._status_counts[new_status] += 1

            if record.zone_id:
                self._zone_status_counts[record.zone_id][old_status] -= 1
                self._zone_status_counts[record.zone_id][new_status] += 1

            record.status = new_status

    def update_driver_zone(self, driver_id: str, new_zone_id: str) -> None:
        with self._lock:
            if driver_id not in self._drivers:
                return

            record = self._drivers[driver_id]
            old_zone_id = record.zone_id

            if old_zone_id:
                self._zone_status_counts[old_zone_id][record.status] -= 1

            if new_zone_id not in self._zone_status_counts:
                self._zone_status_counts[new_zone_id] = {
                    "available": 0,
                    "offline": 0,
                    "en_route_pickup": 0,
                    "on_trip": 0,
                }
            self._zone_status_counts[new_zone_id][record.status] += 1

            record.zone_id = new_zone_id

    def update_driver_location(self, driver_id: str, location: tuple[float, float]) -> None:
        with self._lock:
            if driver_id not in self._drivers:
                return

            self._drivers[driver_id].location = location

    def unregister_driver(self, driver_id: str) -> None:
        with self._lock:
            if driver_id not in self._drivers:
                return

            record = self._drivers[driver_id]
            self._status_counts[record.status] -= 1

            if record.zone_id:
                self._zone_status_counts[record.zone_id][record.status] -= 1

            del self._drivers[driver_id]

    def get_status_count(self, status: str) -> int:
        with self._lock:
            return self._status_counts.get(status, 0)

    def get_zone_driver_count(self, zone_id: str, status: str) -> int:
        with self._lock:
            if zone_id not in self._zone_status_counts:
                return 0
            return self._zone_status_counts[zone_id].get(status, 0)

    def get_available_drivers_in_zone(self, zone_id: str) -> list[str]:
        with self._lock:
            return [
                driver_id
                for driver_id, record in self._drivers.items()
                if record.zone_id == zone_id and record.status == "available"
            ]

    def get_all_status_counts(self) -> dict[str, int]:
        with self._lock:
            return self._status_counts.copy()

    def clear(self) -> None:
        """Clear all registry state for simulation reset."""
        with self._lock:
            self._drivers.clear()
            self._status_counts = {
                "available": 0,
                "offline": 0,
                "en_route_pickup": 0,
                "on_trip": 0,
            }
            self._zone_status_counts.clear()
