import json
import logging

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError

logger = logging.getLogger(__name__)

SNAPSHOT_TTL = 1800  # 30 minutes


class StateSnapshotManager:
    """Manages state snapshots in Redis for client reconnection."""

    def __init__(self, client: aioredis.Redis):
        self._client = client

    async def store_driver(self, data: dict) -> None:
        driver_id = data["driver_id"]
        key = f"snapshot:drivers:{driver_id}"

        snapshot = {
            "driver_id": driver_id,
            "location": data.get("location"),
            "heading": data.get("heading"),
            "status": data.get("status"),
            "trip_id": data.get("trip_id"),
            "recent_path": data.get("recent_path", [])[-10:],
        }

        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
        except ConnectionError as e:
            logger.error(f"Failed to store driver snapshot {driver_id}: {e}")

    async def store_trip(self, data: dict) -> None:
        trip_id = data["trip_id"]
        key = f"snapshot:trips:{trip_id}"

        snapshot = {
            "trip_id": trip_id,
            "state": data.get("state"),
            "pickup": data.get("pickup"),
            "dropoff": data.get("dropoff"),
            "driver_id": data.get("driver_id"),
            "rider_id": data.get("rider_id"),
            "fare": data.get("fare"),
            "surge_multiplier": data.get("surge_multiplier"),
        }

        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
        except ConnectionError as e:
            logger.error(f"Failed to store trip snapshot {trip_id}: {e}")

    async def store_surge(self, data: dict) -> None:
        zone_id = data["zone_id"]
        key = f"snapshot:surge:{zone_id}"

        snapshot = {
            "zone_id": zone_id,
            "multiplier": data.get("multiplier"),
            "updated_at": data.get("updated_at"),
        }

        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
        except ConnectionError as e:
            logger.error(f"Failed to store surge snapshot {zone_id}: {e}")

    async def remove_driver(self, driver_id: str) -> None:
        key = f"snapshot:drivers:{driver_id}"
        try:
            await self._client.delete(key)
        except ConnectionError as e:
            logger.error(f"Failed to remove driver snapshot {driver_id}: {e}")

    async def remove_trip(self, trip_id: str) -> None:
        key = f"snapshot:trips:{trip_id}"
        try:
            await self._client.delete(key)
        except ConnectionError as e:
            logger.error(f"Failed to remove trip snapshot {trip_id}: {e}")

    async def get_all_drivers(self) -> list[dict]:
        drivers = []
        try:
            async for key in self._client.scan_iter(match="snapshot:drivers:*"):
                data = await self._client.get(key)
                if data:
                    drivers.append(json.loads(data))
        except ConnectionError as e:
            logger.error(f"Failed to get driver snapshots: {e}")
        return drivers

    async def get_all_trips(self) -> list[dict]:
        trips = []
        try:
            async for key in self._client.scan_iter(match="snapshot:trips:*"):
                data = await self._client.get(key)
                if data:
                    trips.append(json.loads(data))
        except ConnectionError as e:
            logger.error(f"Failed to get trip snapshots: {e}")
        return trips

    async def get_all_surges(self) -> dict[str, float]:
        surges = {}
        try:
            async for key in self._client.scan_iter(match="snapshot:surge:*"):
                data = await self._client.get(key)
                if data:
                    parsed = json.loads(data)
                    surges[parsed["zone_id"]] = parsed["multiplier"]
        except ConnectionError as e:
            logger.error(f"Failed to get surge snapshots: {e}")
        return surges

    async def get_snapshot(self) -> dict:
        return {
            "drivers": await self.get_all_drivers(),
            "trips": await self.get_all_trips(),
            "surge": await self.get_all_surges(),
        }
