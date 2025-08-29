"""Redis pub/sub subscriber for WebSocket fan-out."""

import asyncio
import contextlib
import json
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Map Redis channels to WebSocket message types
CHANNEL_TO_MESSAGE_TYPE = {
    "driver-updates": "driver_update",
    "rider-updates": "rider_update",
    "trip-updates": "trip_update",
    "surge-updates": "surge_update",
}


class RedisSubscriber:
    """Subscribes to Redis pub/sub and broadcasts to WebSocket clients."""

    def __init__(self, redis_client, connection_manager):
        self.redis_client = redis_client
        self.connection_manager = connection_manager
        self.channels = [
            "driver-updates",
            "rider-updates",
            "trip-updates",
            "surge-updates",
        ]
        self.task = None
        self.reconnect_delay = 5

    async def start(self):
        self.task = asyncio.create_task(self._subscribe_and_fanout())

    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    def _transform_event(self, channel: str, data: dict) -> dict | None:
        """Transform backend event to frontend-expected format."""
        message_type = CHANNEL_TO_MESSAGE_TYPE.get(channel)
        if not message_type:
            return None

        # Check if this is a GPS ping event (has entity_type field)
        is_gps_ping = "entity_type" in data

        if channel == "driver-updates":
            # For GPS pings, infer status from trip_id
            if is_gps_ping:
                status = "busy" if data.get("trip_id") else "online"
            else:
                status = data.get("status") or data.get("new_status", "offline")

            # Extract lat/lon from location tuple
            location = data.get("location") or data.get("home_location") or [0, 0]
            lat, lon = location[0], location[1]

            return {
                "type": message_type,
                "data": {
                    "id": data.get("driver_id") or data.get("entity_id"),
                    "latitude": lat,
                    "longitude": lon,
                    "status": status,
                    "rating": data.get("rating", 5.0),
                    "zone": data.get("zone", "unknown"),
                },
            }
        elif channel == "rider-updates":
            # For GPS pings, rider is in trip if trip_id exists
            if is_gps_ping:
                status = "in_transit" if data.get("trip_id") else "waiting"
            else:
                status = data.get("status", "waiting")
                # Map idle -> waiting for frontend compatibility
                if status == "idle":
                    status = "waiting"

            # Extract lat/lon from location tuple
            location = data.get("location") or data.get("home_location") or [0, 0]
            lat, lon = location[0], location[1]

            return {
                "type": message_type,
                "data": {
                    "id": data.get("rider_id") or data.get("entity_id"),
                    "latitude": lat,
                    "longitude": lon,
                    "status": status,
                },
            }
        elif channel == "trip-updates":
            return {
                "type": message_type,
                "data": {
                    "id": data.get("trip_id"),
                    "status": data.get("state"),
                    "driver_id": data.get("driver_id"),
                    "rider_id": data.get("rider_id"),
                    "route": {
                        "pickup": data.get("pickup_location"),
                        "dropoff": data.get("dropoff_location"),
                    },
                },
            }
        elif channel == "surge-updates":
            return {
                "type": message_type,
                "data": {
                    "zone": data.get("zone_id"),
                    "multiplier": data.get("multiplier", 1.0),
                },
            }

        return None

    async def _subscribe_and_fanout(self):
        while True:
            try:
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(*self.channels)

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            channel = message["channel"]
                            if isinstance(channel, bytes):
                                channel = channel.decode("utf-8")

                            data = json.loads(message["data"])
                            transformed = self._transform_event(channel, data)

                            if transformed:
                                await self.connection_manager.broadcast(transformed)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON from Redis: {message['data']}")
                        except Exception as e:
                            logger.warning(f"Error broadcasting message: {e}")

            except redis.ConnectionError:
                logger.error(f"Redis disconnected, reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
            except asyncio.CancelledError:
                break
