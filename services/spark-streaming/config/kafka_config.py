"""Kafka consumer configuration for streaming jobs."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class KafkaConfig:
    """Configuration for Kafka consumer in streaming jobs."""

    bootstrap_servers: str
    schema_registry_url: str
    consumer_group: Optional[str] = None
    starting_offsets: str = "earliest"
    fail_on_data_loss: bool = False
    topic: Optional[str] = None
    topics: Optional[list[str]] = None

    def __post_init__(self):
        if not self.bootstrap_servers:
            raise ValueError("bootstrap_servers must not be empty")
        if not self.schema_registry_url:
            raise ValueError("schema_registry_url must not be empty")

    def to_spark_options(
        self, topic: Optional[str] = None, topics: Optional[list[str]] = None
    ) -> dict:
        """Generate Spark readStream options for Kafka.

        Args:
            topic: Single topic to subscribe to (for backward compatibility)
            topics: List of topics to subscribe to (for multi-topic jobs)

        Returns:
            Dictionary of Spark Kafka options

        Priority: topics parameter > topics field > topic parameter > topic field
        """
        options = {
            "kafka.bootstrap.servers": self.bootstrap_servers,
            "startingOffsets": self.starting_offsets,
            "failOnDataLoss": str(self.fail_on_data_loss).lower(),
        }

        # Normalize to list: prioritize function args, then instance fields
        topic_list = topics or self.topics
        if not topic_list and (topic or self.topic):
            topic_list = [topic or self.topic]

        if topic_list:
            options["subscribe"] = ",".join(topic_list)
        else:
            options["subscribePattern"] = ".*"

        if self.consumer_group:
            options["kafka.group.id"] = self.consumer_group

        return options
