from dataclasses import dataclass


@dataclass
class DriverRecord:
    driver_id: str
    status: str
    zone_id: str | None = None
    location: tuple[float, float] | None = None


class DriverRegistry:
    def __init__(self):
        self._drivers: dict[str, DriverRecord] = {}
        self._status_counts: dict[str, int] = {
            "online": 0,
            "offline": 0,
            "busy": 0,
            "en_route_pickup": 0,
            "en_route_destination": 0,
        }
        self._zone_status_counts: dict[str, dict[str, int]] = {}

    def register_driver(
        self,
        driver_id: str,
        status: str,
        zone_id: str | None = None,
        location: tuple[float, float] | None = None,
    ):
        record = DriverRecord(
            driver_id=driver_id, status=status, zone_id=zone_id, location=location
        )
        self._drivers[driver_id] = record
        self._status_counts[status] += 1

        if zone_id:
            if zone_id not in self._zone_status_counts:
                self._zone_status_counts[zone_id] = {
                    "online": 0,
                    "offline": 0,
                    "busy": 0,
                    "en_route_pickup": 0,
                    "en_route_destination": 0,
                }
            self._zone_status_counts[zone_id][status] += 1

    def update_driver_status(self, driver_id: str, new_status: str):
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

    def update_driver_zone(self, driver_id: str, new_zone_id: str):
        if driver_id not in self._drivers:
            return

        record = self._drivers[driver_id]
        old_zone_id = record.zone_id

        if old_zone_id:
            self._zone_status_counts[old_zone_id][record.status] -= 1

        if new_zone_id not in self._zone_status_counts:
            self._zone_status_counts[new_zone_id] = {
                "online": 0,
                "offline": 0,
                "busy": 0,
                "en_route_pickup": 0,
                "en_route_destination": 0,
            }
        self._zone_status_counts[new_zone_id][record.status] += 1

        record.zone_id = new_zone_id

    def update_driver_location(self, driver_id: str, location: tuple[float, float]):
        if driver_id not in self._drivers:
            return

        self._drivers[driver_id].location = location

    def unregister_driver(self, driver_id: str):
        if driver_id not in self._drivers:
            return

        record = self._drivers[driver_id]
        self._status_counts[record.status] -= 1

        if record.zone_id:
            self._zone_status_counts[record.zone_id][record.status] -= 1

        del self._drivers[driver_id]

    def get_status_count(self, status: str) -> int:
        return self._status_counts.get(status, 0)

    def get_zone_driver_count(self, zone_id: str, status: str) -> int:
        if zone_id not in self._zone_status_counts:
            return 0
        return self._zone_status_counts[zone_id].get(status, 0)

    def get_available_drivers_in_zone(self, zone_id: str) -> list[str]:
        return [
            driver_id
            for driver_id, record in self._drivers.items()
            if record.zone_id == zone_id and record.status == "online"
        ]

    def get_all_status_counts(self) -> dict[str, int]:
        return self._status_counts.copy()
