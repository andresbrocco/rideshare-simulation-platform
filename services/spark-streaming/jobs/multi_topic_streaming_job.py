"""Multi-topic streaming job base class."""

from typing import Any, Optional

from pyspark.sql.functions import col, date_format

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class MultiTopicStreamingJob(BaseStreamingJob):
    """Base class for streaming jobs that consume from multiple Kafka topics.

    Routes messages to appropriate Bronze Delta tables based on topic metadata
    provided by Kafka when subscribing to multiple topics.

    Subclasses should override get_topic_names() to define which topics to consume.
    """

    def get_topic_names(self) -> list[str]:
        """Return list of topics this job should consume.

        Must be overridden by subclasses.

        Example:
            return ["trips", "payments", "ratings"]
        """
        raise NotImplementedError("Subclasses must implement get_topic_names()")

    @property
    def topic_names(self) -> list[str]:
        """Multiple topics to consume from."""
        return self.get_topic_names()

    @property
    def partition_columns(self) -> Optional[list]:
        """All Bronze tables use _ingestion_date partitioning."""
        return ["_ingestion_date"]

    def get_bronze_path(self, topic: str) -> str:
        """Map Kafka topic name to Bronze Delta table path.

        Default implementation converts topic name to Bronze table path:
        - "trips" -> "s3a://rideshare-bronze/bronze_trips/"
        - "gps_pings" -> "s3a://rideshare-bronze/bronze_gps_pings/"
        - "driver_status" -> "s3a://rideshare-bronze/bronze_driver_status/"

        Args:
            topic: Kafka topic name

        Returns:
            S3 path to Bronze Delta table
        """
        table_name = topic.replace("-", "_")
        return f"s3a://rideshare-bronze/bronze_{table_name}/"

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch with topic-based routing.

        Routes messages to appropriate Bronze tables based on 'topic' column
        provided by Kafka when subscribing to multiple topics.

        Args:
            df: Micro-batch DataFrame containing 'topic' column
            batch_id: Spark Structured Streaming batch ID

        Returns:
            Original DataFrame (unchanged)
        """
        # Use isEmpty() instead of count() - stops at first row, avoids full scan
        if df.isEmpty():
            return df

        for topic in self.get_topic_names():
            topic_df = df.filter(col("topic") == topic)

            # Add partition column and drop the 'topic' column (not part of Bronze schema)
            partitioned_df = topic_df.withColumn(
                "_ingestion_date", date_format(col("_ingested_at"), "yyyy-MM-dd")
            ).drop("topic")

            # Use isEmpty() for efficiency - avoids materializing count
            if partitioned_df.isEmpty():
                continue

            bronze_path = self.get_bronze_path(topic)

            write_builder = partitioned_df.write.format("delta").mode("append")
            if self.partition_columns:
                write_builder = write_builder.partitionBy(*self.partition_columns)
            write_builder.save(bronze_path)

        return df

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available.

        Spark Structured Streaming handles checkpoint recovery automatically
        when a checkpoint location is provided. This method is a no-op for
        multi-topic jobs.
        """
        pass
