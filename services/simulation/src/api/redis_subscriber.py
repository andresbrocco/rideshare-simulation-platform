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
        self._subscribed = asyncio.Event()

    async def start(self):
        """Start the subscriber and wait for subscription to be established."""
        self.task = asyncio.create_task(self._subscribe_and_fanout())
        # Wait for subscription to be established before returning
        # This ensures we're ready to receive messages before the API accepts connections
        try:
            await asyncio.wait_for(self._subscribed.wait(), timeout=10.0)
            logger.info("Redis subscriber ready - subscribed to all channels")
        except TimeoutError:
            logger.warning("Redis subscription timeout - proceeding anyway")

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
            # Extract lat/lon from location tuple
            location = data.get("location") or data.get("home_location") or [0, 0]
            lat, lon = location[0], location[1]

            if is_gps_ping:
                # GPS pings: send position update with heading and route progress (use "gps_ping" type)
                return {
                    "type": "gps_ping",
                    "data": {
                        "id": data.get("entity_id"),
                        "entity_type": "driver",
                        "latitude": lat,
                        "longitude": lon,
                        "heading": data.get("heading", 0),
                        "timestamp": data.get("timestamp"),
                        "trip_id": data.get("trip_id"),
                        "route_progress_index": data.get("route_progress_index"),
                        "pickup_route_progress_index": data.get(
                            "pickup_route_progress_index"
                        ),
                    },
                }
            else:
                # Status change events: include full driver info
                status = data.get("status") or data.get("new_status", "offline")
                return {
                    "type": message_type,
                    "data": {
                        "id": data.get("driver_id") or data.get("entity_id"),
                        "latitude": lat,
                        "longitude": lon,
                        "status": status,
                        "rating": data.get("rating", 5.0),
                        "zone": data.get("zone", "unknown"),
                        "heading": data.get("heading", 0),
                    },
                }
        elif channel == "rider-updates":
            # Extract lat/lon from location tuple
            location = data.get("location") or data.get("home_location") or [0, 0]
            lat, lon = location[0], location[1]

            if is_gps_ping:
                # Use trip_state from event if available, fallback to inference
                trip_state = data.get("trip_state")
                if not trip_state:
                    trip_state = "started" if data.get("trip_id") else "offline"

                # Return as gps_ping type for rider position updates during trips
                return {
                    "type": "gps_ping",
                    "data": {
                        "id": data.get("entity_id"),
                        "entity_type": "rider",
                        "latitude": lat,
                        "longitude": lon,
                        "trip_state": trip_state,
                        "timestamp": data.get("timestamp"),
                    },
                }
            else:
                status = data.get("status", "waiting")
                # Map offline -> waiting for frontend compatibility
                if status == "offline":
                    status = "waiting"

                # For profile events (rider.created), default trip_state to offline
                trip_state = data.get("trip_state", "offline")

                return {
                    "type": message_type,
                    "data": {
                        "id": data.get("rider_id") or data.get("entity_id"),
                        "latitude": lat,
                        "longitude": lon,
                        "status": status,
                        "trip_state": trip_state,
                    },
                }
        elif channel == "trip-updates":
            # Extract coordinates from location tuples
            pickup_loc = data.get("pickup_location") or [0, 0]
            dropoff_loc = data.get("dropoff_location") or [0, 0]

            # Extract status from event_type (e.g., "trip.driver_en_route" -> "driver_en_route")
            event_type = data.get("event_type", "")
            if event_type.startswith("trip."):
                status = event_type[5:]  # Remove "trip." prefix
            else:
                status = data.get("status") or data.get("state") or "unknown"

            return {
                "type": message_type,
                "data": {
                    "id": data.get("id") or data.get("trip_id"),
                    "status": status,
                    "driver_id": data.get("driver_id"),
                    "rider_id": data.get("rider_id"),
                    "pickup_latitude": pickup_loc[0],
                    "pickup_longitude": pickup_loc[1],
                    "dropoff_latitude": dropoff_loc[0],
                    "dropoff_longitude": dropoff_loc[1],
                    "route": data.get("route") or [],
                    "pickup_route": data.get("pickup_route") or [],
                    "route_progress_index": data.get("route_progress_index"),
                    "pickup_route_progress_index": data.get(
                        "pickup_route_progress_index"
                    ),
                },
            }
        elif channel == "surge-updates":
            return {
                "type": message_type,
                "data": {
                    "zone": data.get("zone_id"),
                    "multiplier": data.get("new_multiplier", 1.0),
                },
            }

        return None

    async def _subscribe_and_fanout(self):
        while True:
            try:
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(*self.channels)
                # Signal that subscription is established
                self._subscribed.set()
                logger.info(f"Subscribed to Redis channels: {self.channels}")

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
                            logger.warning(
                                f"Invalid JSON from Redis: {message['data']}"
                            )
                        except Exception as e:
                            logger.warning(f"Error broadcasting message: {e}")

            except redis.ConnectionError:
                logger.error(
                    f"Redis disconnected, reconnecting in {self.reconnect_delay}s..."
                )
                await asyncio.sleep(self.reconnect_delay)
            except asyncio.CancelledError:
                break
