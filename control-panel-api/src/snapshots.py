import json
import logging

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError

logger = logging.getLogger(__name__)

SNAPSHOT_TTL = 1800


class StateSnapshotManager:
    """Manages state snapshots in Redis for client reconnection."""

    def __init__(self, client: aioredis.Redis):
        self._client = client

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
