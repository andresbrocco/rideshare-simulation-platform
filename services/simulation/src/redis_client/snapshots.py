from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from redis.exceptions import ConnectionError

from metrics import get_metrics_collector
from metrics.prometheus_exporter import observe_latency

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

SNAPSHOT_TTL = 1800  # 30 minutes


class StateSnapshotManager:
    """Manages state snapshots in Redis for client reconnection."""

    def __init__(self, client: aioredis.Redis[bytes]):
        self._client = client

    async def store_driver(self, data: dict[str, Any]) -> None:
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

        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to store driver snapshot {driver_id}: {e}")

    async def store_trip(self, data: dict[str, Any]) -> None:
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

        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to store trip snapshot {trip_id}: {e}")

    async def store_surge(self, data: dict[str, Any]) -> None:
        zone_id = data["zone_id"]
        key = f"snapshot:surge:{zone_id}"

        snapshot = {
            "zone_id": zone_id,
            "multiplier": data.get("multiplier"),
            "updated_at": data.get("updated_at"),
        }

        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            await self._client.setex(key, SNAPSHOT_TTL, json.dumps(snapshot))
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to store surge snapshot {zone_id}: {e}")

    async def remove_driver(self, driver_id: str) -> None:
        key = f"snapshot:drivers:{driver_id}"
        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            await self._client.delete(key)
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to remove driver snapshot {driver_id}: {e}")

    async def remove_trip(self, trip_id: str) -> None:
        key = f"snapshot:trips:{trip_id}"
        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            await self._client.delete(key)
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to remove trip snapshot {trip_id}: {e}")

    async def get_all_drivers(self) -> list[dict[str, Any]]:
        drivers = []
        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            async for key in self._client.scan_iter(match="snapshot:drivers:*"):
                data = await self._client.get(key)
                if data:
                    drivers.append(json.loads(data))
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to get driver snapshots: {e}")
        return drivers

    async def get_all_trips(self) -> list[dict[str, Any]]:
        trips = []
        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            async for key in self._client.scan_iter(match="snapshot:trips:*"):
                data = await self._client.get(key)
                if data:
                    trips.append(json.loads(data))
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to get trip snapshots: {e}")
        return trips

    async def get_all_surges(self) -> dict[str, float]:
        surges: dict[str, float] = {}
        collector = get_metrics_collector()
        start_time = time.perf_counter()
        try:
            async for key in self._client.scan_iter(match="snapshot:surge:*"):
                data = await self._client.get(key)
                if data:
                    parsed = json.loads(data)
                    surges[parsed["zone_id"]] = parsed["multiplier"]
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("redis", latency_ms)
            observe_latency("redis", latency_ms)
        except ConnectionError as e:
            collector.record_error("redis", "connection_error")
            logger.error(f"Failed to get surge snapshots: {e}")
        return surges

    async def get_snapshot(self) -> dict[str, Any]:
        return {
            "drivers": await self.get_all_drivers(),
            "trips": await self.get_all_trips(),
            "surge": await self.get_all_surges(),
        }
