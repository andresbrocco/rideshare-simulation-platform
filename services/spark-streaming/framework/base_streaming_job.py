"""Base class for Spark Structured Streaming jobs."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from spark_streaming.config.kafka_config import KafkaConfig
from spark_streaming.config.checkpoint_config import CheckpointConfig
from spark_streaming.config.delta_write_config import DeltaWriteConfig
from spark_streaming.utils.error_handler import ErrorHandler


class BaseStreamingJob(ABC):
    """Abstract base class for all Bronze layer streaming jobs."""

    def __init__(
        self,
        spark: Any,
        kafka_config: KafkaConfig,
        checkpoint_config: CheckpointConfig,
        error_handler: ErrorHandler,
        delta_write_config: Optional[DeltaWriteConfig] = None,
    ):
        self._spark = spark
        self._kafka_config = kafka_config
        self._checkpoint_config = checkpoint_config
        self._error_handler = error_handler
        self._delta_write_config = delta_write_config or DeltaWriteConfig()
        self._query = None
        self.starting_offsets = None

    @property
    def topic_name(self) -> Optional[str]:
        """Single topic to consume from (for backward compatibility).

        Subclasses should override either this or topic_names, not both.
        """
        return None

    @property
    def topic_names(self) -> Optional[list[str]]:
        """Multiple topics to consume from (for consolidated jobs).

        Subclasses should override either this or topic_name, not both.
        """
        return None

    @property
    def bronze_table_path(self) -> Optional[str]:
        """Path to the Bronze Delta table.

        Single-topic jobs must override this property.
        Multi-topic jobs typically don't use this (routing happens in process_batch).
        """
        return None

    @abstractmethod
    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of data."""
        pass

    def _validate_topic_config(self):
        """Ensure at least one topic configuration is provided."""
        if not self.topic_name and not self.topic_names:
            raise ValueError("Either topic_name or topic_names must be defined")
        if self.topic_name and self.topic_names:
            raise ValueError("Cannot define both topic_name and topic_names")

    @property
    def partition_columns(self) -> Optional[list]:
        """Columns to partition by. Override to enable partitioning."""
        return None

    def _has_active_spark_context(self) -> bool:
        """Check if there's an active Spark context."""
        try:
            from pyspark import SparkContext

            return SparkContext._active_spark_context is not None
        except (ImportError, AttributeError):
            return False

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
    def delta_write_config(self) -> DeltaWriteConfig:
        return self._delta_write_config

    @property
    def output_format(self) -> str:
        return "delta"

    def start(self):
        """Start the streaming job."""
        from pyspark.sql.functions import (
            col,
            current_timestamp,
        )
        from pyspark.sql.types import StringType

        # Validate topic configuration
        self._validate_topic_config()

        # Get Kafka options based on single or multi-topic mode
        if self.topic_names:
            kafka_options = self._kafka_config.to_spark_options(topics=self.topic_names)
        else:
            kafka_options = self._kafka_config.to_spark_options(topic=self.topic_name)

        raw_df = self._spark.readStream.format("kafka").options(**kafka_options).load()

        # Select columns - include 'topic' for multi-topic routing
        if self.topic_names:
            df = raw_df.select(
                col("topic"),  # topic column for routing
                col("value").cast(StringType()).alias("_raw_value"),
                col("partition").alias("_kafka_partition"),
                col("offset").alias("_kafka_offset"),
                col("timestamp").alias("_kafka_timestamp"),
                current_timestamp().alias("_ingested_at"),
            )
        else:
            df = raw_df.select(
                col("value").cast(StringType()).alias("_raw_value"),
                col("partition").alias("_kafka_partition"),
                col("offset").alias("_kafka_offset"),
                col("timestamp").alias("_kafka_timestamp"),
                current_timestamp().alias("_ingested_at"),
            )

        trigger_config: dict[str, str | bool] = {}
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
