"""Stream processor entry point."""

import logging
import os
import signal
import sys

from confluent_kafka.admin import AdminClient, NewTopic

from .api import start_api_server_thread
from .logging_setup import setup_logging
from .processor import StreamProcessor
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Topics required for the stream processor
REQUIRED_TOPICS = [
    "gps_pings",
    "trips",
    "driver_status",
    "surge_updates",
    "driver_profiles",
    "rider_profiles",
]


def ensure_topics_exist(settings: Settings) -> None:
    """Pre-create Kafka topics if they don't exist.

    This ensures the consumer can get partition assignments immediately
    when subscribing, rather than waiting for topics to be auto-created
    by the simulation producer.
    """
    admin_config = {
        "bootstrap.servers": settings.kafka.bootstrap_servers,
    }
    admin = AdminClient(admin_config)

    # Get existing topics
    try:
        metadata = admin.list_topics(timeout=10.0)
        existing_topics = set(metadata.topics.keys())
    except Exception as e:
        logger.warning(f"Failed to list topics: {e}")
        return

    # Create missing topics
    topics_to_create = []
    for topic_name in REQUIRED_TOPICS:
        if topic_name not in existing_topics:
            # Create with 1 partition and replication factor 1 (single broker)
            topics_to_create.append(
                NewTopic(topic_name, num_partitions=1, replication_factor=1)
            )

    if not topics_to_create:
        logger.info(f"All {len(REQUIRED_TOPICS)} required topics already exist")
        return

    logger.info(
        f"Creating {len(topics_to_create)} missing topics: {[t.topic for t in topics_to_create]}"
    )

    # Create topics
    futures = admin.create_topics(topics_to_create)

    # Wait for creation to complete
    for topic_name, future in futures.items():
        try:
            future.result()  # Block until topic is created
            logger.info(f"Created topic: {topic_name}")
        except Exception as e:
            # Topic might already exist (race condition) - that's OK
            if "TopicExistsException" in str(
                type(e).__name__
            ) or "TOPIC_ALREADY_EXISTS" in str(e):
                logger.info(f"Topic {topic_name} already exists")
            else:
                logger.warning(f"Failed to create topic {topic_name}: {e}")


def main() -> None:
    """Main entry point for the stream processor."""
    # Load settings
    settings = get_settings()

    # Configure logging using centralized setup
    setup_logging(
        level=settings.log_level,
        json_output=os.environ.get("LOG_FORMAT") == "json",
        environment=os.environ.get("ENVIRONMENT", "development"),
    )

    logger.info("Starting stream processor...")
    logger.info(f"Kafka: {settings.kafka.bootstrap_servers}")
    logger.info(f"Redis: {settings.redis.host}:{settings.redis.port}")
    logger.info(f"Window size: {settings.processor.window_size_ms}ms")
    logger.info(f"Strategy: {settings.processor.aggregation_strategy}")

    # Pre-create topics to ensure consumer can get partition assignments
    ensure_topics_exist(settings)

    # Start HTTP API server in background thread (for health checks and metrics)
    logger.info(f"Starting HTTP API on {settings.api.host}:{settings.api.port}")
    start_api_server_thread(settings.api.host, settings.api.port)

    # Create processor
    processor = StreamProcessor(settings)

    # Handle shutdown signals
    def shutdown_handler(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        processor.stop()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Start processing
    try:
        processor.start()
    except Exception as e:
        logger.exception(f"Fatal error in stream processor: {e}")
        sys.exit(1)

    logger.info("Stream processor exited")


if __name__ == "__main__":
    main()
