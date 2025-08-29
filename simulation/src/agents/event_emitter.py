"""EventEmitter mixin for agent event emission to Kafka and Redis."""

import logging

from pydantic import BaseModel

from kafka.producer import KafkaProducer
from redis_client.publisher import RedisPublisher

logger = logging.getLogger(__name__)

GPS_PING_INTERVAL = 5


class EventEmitter:
    """Mixin class for emitting events to Kafka and Redis."""

    def __init__(
        self,
        kafka_producer: KafkaProducer | None,
        redis_publisher: RedisPublisher | None,
    ):
        self._kafka_producer = kafka_producer
        self._redis_publisher = redis_publisher

    def _emit_to_kafka(self, topic: str, key: str, event: BaseModel) -> None:
        if self._kafka_producer is None:
            return

        try:
            json_str = event.model_dump_json()
            self._kafka_producer.produce(topic=topic, key=key, value=json_str)
        except Exception as e:
            logger.error(f"Failed to emit event to Kafka topic {topic}: {e}")

    async def _emit_to_redis(self, channel: str, event: BaseModel) -> None:
        if self._redis_publisher is None:
            return

        try:
            message = event.model_dump(mode="json")
            await self._redis_publisher.publish(channel=channel, message=message)
        except Exception as e:
            logger.error(f"Failed to emit event to Redis channel {channel}: {e}")

    async def _emit_event(
        self,
        event: BaseModel,
        kafka_topic: str,
        partition_key: str,
        redis_channel: str | None = None,
    ) -> None:
        self._emit_to_kafka(kafka_topic, partition_key, event)

        if redis_channel:
            await self._emit_to_redis(redis_channel, event)
