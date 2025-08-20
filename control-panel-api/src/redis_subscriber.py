"""Redis pub/sub subscriber for WebSocket fan-out."""

import asyncio
import json
import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


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
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _subscribe_and_fanout(self):
        while True:
            try:
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(*self.channels)

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await self.connection_manager.broadcast(data)
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
