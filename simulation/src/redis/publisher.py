import json
import logging

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError
from simulation.src.pubsub.channels import ALL_CHANNELS

logger = logging.getLogger(__name__)


class RedisPublisher:
    """Async Redis publisher for real-time visualization events."""

    def __init__(self, config: dict):
        self.config = config
        self._client = aioredis.Redis(
            host=config["host"],
            port=config["port"],
            db=config["db"],
            password=config.get("password"),
            decode_responses=True,
        )

    async def publish(self, channel: str, message: dict) -> None:
        if channel not in ALL_CHANNELS:
            raise ValueError(
                f"Channel '{channel}' is not a valid channel. Valid channels: {ALL_CHANNELS}"
            )

        try:
            json_message = json.dumps(message)
            await self._client.publish(channel, json_message)
        except ConnectionError as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")

    async def close(self) -> None:
        await self._client.close()
