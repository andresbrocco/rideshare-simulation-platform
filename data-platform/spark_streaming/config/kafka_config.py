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

    def __post_init__(self):
        if not self.bootstrap_servers:
            raise ValueError("bootstrap_servers must not be empty")
        if not self.schema_registry_url:
            raise ValueError("schema_registry_url must not be empty")

    def to_spark_options(self, topic: Optional[str] = None) -> dict:
        """Generate Spark readStream options for Kafka."""
        options = {
            "kafka.bootstrap.servers": self.bootstrap_servers,
            "startingOffsets": self.starting_offsets,
            "failOnDataLoss": str(self.fail_on_data_loss).lower(),
        }

        if topic or self.topic:
            options["subscribe"] = topic or self.topic
        else:
            options["subscribePattern"] = ".*"

        if self.consumer_group:
            options["kafka.group.id"] = self.consumer_group

        return options
