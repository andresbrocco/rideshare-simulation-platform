"""Base class for Spark Structured Streaming jobs."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.utils.error_handler import ErrorHandler


class BaseStreamingJob(ABC):
    """Abstract base class for all Bronze layer streaming jobs."""

    def __init__(
        self,
        spark: Any,
        kafka_config: KafkaConfig,
        checkpoint_config: CheckpointConfig,
        error_handler: ErrorHandler,
    ):
        self._spark = spark
        self._kafka_config = kafka_config
        self._checkpoint_config = checkpoint_config
        self._error_handler = error_handler
        self._query = None
        self.starting_offsets = None

    @property
    @abstractmethod
    def topic_name(self) -> str:
        """Kafka topic to consume from."""
        pass

    @property
    @abstractmethod
    def bronze_table_path(self) -> str:
        """Path to the Bronze Delta table."""
        pass

    @abstractmethod
    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of data."""
        pass

    @property
    def kafka_config(self) -> KafkaConfig:
        return self._kafka_config

    @property
    def checkpoint_config(self) -> CheckpointConfig:
        return self._checkpoint_config

    @property
    def error_handler(self) -> ErrorHandler:
        return self._error_handler

    @property
    def output_format(self) -> str:
        return "delta"

    def start(self):
        """Start the streaming job."""
        kafka_options = self._kafka_config.to_spark_options(topic=self.topic_name)

        df = self._spark.readStream.format("kafka").options(**kafka_options).load()

        trigger_config = {}
        if self._checkpoint_config.trigger_interval == "availableNow":
            trigger_config["availableNow"] = True
        else:
            trigger_config["processingTime"] = self._checkpoint_config.trigger_interval

        self._query = (
            df.writeStream.format("delta")
            .option("checkpointLocation", self._checkpoint_config.checkpoint_path)
            .trigger(**trigger_config)
            .foreachBatch(self.process_batch)
            .start(self.bronze_table_path)
        )

        return self._query

    def stop(self):
        """Stop the streaming job gracefully."""
        if self._query:
            self._query.stop()

    def await_termination(self, timeout: Optional[int] = None):
        """Wait for the streaming job to terminate."""
        if self._query:
            self._query.awaitTermination(timeout)

    def get_last_progress(self) -> Optional[dict]:
        """Get the last progress report from the streaming query."""
        if self._query:
            return self._query.lastProgress
        return None

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available."""
        pass

    def get_starting_options(self) -> dict:
        """Get starting options including recovered offsets."""
        return {"startingOffsets": self.starting_offsets}
