"""Streaming job for surge-updates topic ingestion to Bronze layer."""

from typing import Any, Optional
from pyspark.sql.functions import date_format, col

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class SurgeUpdatesStreamingJob(BaseStreamingJob):
    """Streaming job for surge-updates topic."""

    @property
    def topic_name(self) -> str:
        return "surge-updates"

    @property
    def bronze_table_path(self) -> str:
        return "s3a://rideshare-bronze/bronze_surge_updates/"

    @property
    def partition_columns(self) -> Optional[list]:
        return ["_ingestion_date"]

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of Kafka messages."""
        if self._has_active_spark_context() and self.partition_columns:
            partitioned_df = df.withColumn(
                "_ingestion_date", date_format(col("_ingested_at"), "yyyy-MM-dd")
            )
            write_builder = partitioned_df.write.format("delta").mode("append")
            write_builder = write_builder.partitionBy(*self.partition_columns)
        else:
            write_builder = df.write.format("delta").mode("append")

        write_builder.save(self.bronze_table_path)
        return df

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available."""
        self.starting_offsets = {f"{self.topic_name}-0": 50}


if __name__ == "__main__":
    import os
    from pyspark.sql import SparkSession
    from spark_streaming.config.kafka_config import KafkaConfig
    from spark_streaming.config.checkpoint_config import CheckpointConfig
    from spark_streaming.utils.error_handler import ErrorHandler

    spark = SparkSession.builder.appName("SurgeUpdatesStreamingJob").getOrCreate()

    kafka_config = KafkaConfig(
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
        schema_registry_url=os.environ.get(
            "SCHEMA_REGISTRY_URL", "http://schema-registry:8081"
        ),
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path=os.environ.get(
            "CHECKPOINT_PATH", "s3a://rideshare-checkpoints/surge-updates/"
        ),
        trigger_interval=os.environ.get("TRIGGER_INTERVAL", "10 seconds"),
    )
    error_handler = ErrorHandler(
        dlq_table_path="s3a://rideshare-bronze/dlq_surge_updates/"
    )

    job = SurgeUpdatesStreamingJob(
        spark, kafka_config, checkpoint_config, error_handler
    )
    query = job.start()
    query.awaitTermination()
