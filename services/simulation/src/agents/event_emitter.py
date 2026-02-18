"""EventEmitter mixin for agent event emission to Kafka.

Note: Redis publishing has been removed from this module. All events now flow
through Kafka only. The stream-processor service consumes from Kafka and
publishes to Redis with windowed aggregation for GPS pings and pass-through
for other event types. This architecture provides:
- Single point of control for real-time event delivery
- Configurable GPS aggregation to reduce frontend load
- Clean separation between simulation and delivery concerns
"""

import logging
import os
import time

from pydantic import BaseModel

from core.exceptions import NetworkError
from kafka.producer import KafkaProducer
from kafka.serializer_registry import SerializerRegistry
from metrics import get_metrics_collector
from metrics.prometheus_exporter import observe_latency

logger = logging.getLogger(__name__)

# GPS ping intervals in seconds (simulated time).
# Moving agents (drivers in trip, riders in vehicle) ping more frequently.
# Idle drivers (online, waiting for trips) ping less frequently to reduce load.
GPS_PING_INTERVAL_MOVING = int(os.environ.get("GPS_PING_INTERVAL_MOVING", "2"))
GPS_PING_INTERVAL_IDLE = int(os.environ.get("GPS_PING_INTERVAL_IDLE", "10"))

# Profile update interval in seconds (simulated time).
# Default: ~7 simulated days (7 * 24 * 3600 = 604800 seconds).
# Controls how often agents emit profile.updated events for SCD Type 2 tracking.
PROFILE_UPDATE_INTERVAL_SECONDS = int(
    os.environ.get("PROFILE_UPDATE_INTERVAL_SECONDS", str(7 * 24 * 3600))
)

# Mapping from Kafka topic names to metric event types.
# Kept at module level to avoid re-creating the dict on every _emit_event() call.
_TOPIC_TO_EVENT_TYPE: dict[str, str] = {
    "trips": "trip_event",
    "gps_pings": "gps_ping",
    "driver_status": "driver_status",
    "surge_updates": "surge_update",
    "ratings": "rating",
    "payments": "payment",
    "driver_profiles": "driver_profile",
    "rider_profiles": "rider_profile",
}


class EventEmitter:
    """Mixin class for emitting events to Kafka.

    Events flow: Simulation -> Kafka -> Stream Processor -> Redis -> WebSocket
    """

    def __init__(
        self,
        kafka_producer: KafkaProducer | None,
        redis_publisher: object | None = None,  # Kept for backward compatibility
    ):
        self._kafka_producer = kafka_producer
        # redis_publisher is no longer used - stream processor handles Redis
        self._redis_publisher = redis_publisher

    def _emit_to_kafka(self, topic: str, key: str, event: BaseModel) -> None:
        if self._kafka_producer is None:
            return

        collector = get_metrics_collector()
        try:
            start_time = time.perf_counter()

            # Use serializer if Schema Registry is enabled
            serializer = SerializerRegistry.get_serializer(topic)
            if serializer:
                json_str, is_corrupted = serializer.serialize_for_kafka(event, topic)
                if is_corrupted:
                    logger.debug(f"Emitting corrupted event for testing: {topic}")
            else:
                json_str = event.model_dump_json()

            self._kafka_producer.produce(topic=topic, key=key, value=json_str)
            latency_ms = (time.perf_counter() - start_time) * 1000
            collector.record_latency("kafka", latency_ms)
            observe_latency("kafka", latency_ms)
        except NetworkError as e:
            # Transient network errors - log and continue (fire-and-forget for non-critical events)
            collector.record_error("kafka", "network_error")
            logger.warning(f"Kafka emit failed for {topic}: {e}")
        except Exception as e:
            collector.record_error("kafka", type(e).__name__)
            logger.error(
                f"Failed to emit event to Kafka topic {topic}: {e}",
                extra={"topic": topic, "key": key, "event_type": type(event).__name__},
            )

    def _emit_event(
        self,
        event: BaseModel,
        kafka_topic: str,
        partition_key: str,
        redis_channel: str | None = None,  # Kept for backward compatibility
    ) -> None:
        """Emit event to Kafka.

        Args:
            event: Pydantic event model.
            kafka_topic: Kafka topic to publish to.
            partition_key: Key for Kafka partitioning.
            redis_channel: Ignored. Kept for backward compatibility.
                          Stream processor now handles Redis publishing.
        """
        event_type = _TOPIC_TO_EVENT_TYPE.get(kafka_topic, kafka_topic)
        get_metrics_collector().record_event(event_type)

        # Emit to Kafka only - stream processor handles Redis publishing
        self._emit_to_kafka(kafka_topic, partition_key, event)
