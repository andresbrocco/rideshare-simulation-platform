"""Streaming job for low-volume topics ingestion to Bronze layer."""

from spark_streaming.jobs.multi_topic_streaming_job import MultiTopicStreamingJob


class BronzeIngestionLowVolume(MultiTopicStreamingJob):
    """Streaming job for 7 low-volume topics.

    Efficiently shares resources across multiple low-volume topics:
    - trips (4 partitions)
    - driver_status (2 partitions)
    - surge_updates (2 partitions)
    - ratings (2 partitions)
    - payments (2 partitions)
    - driver_profiles (1 partition)
    - rider_profiles (1 partition)

    Writes to 7 separate Bronze Delta tables with topic-specific
    checkpoint paths for clean separation.
    """

    def get_topic_names(self) -> list[str]:
        """Return the list of low-volume topics."""
        return [
            "trips",
            "driver_status",
            "surge_updates",
            "ratings",
            "payments",
            "driver_profiles",
            "rider_profiles",
        ]


if __name__ == "__main__":
    import os
    from pyspark.sql import SparkSession
    from spark_streaming.config.kafka_config import KafkaConfig
    from spark_streaming.config.checkpoint_config import CheckpointConfig
    from spark_streaming.utils.error_handler import ErrorHandler

    spark = (
        SparkSession.builder.appName("BronzeIngestionLowVolume")
        .master("local[2]")
        .config("spark.executor.memory", "768m")
        .config("spark.driver.memory", "768m")
        .getOrCreate()
    )

    kafka_config = KafkaConfig(
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
        schema_registry_url=os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081"),
    )

    checkpoint_config = CheckpointConfig(
        checkpoint_path=os.environ.get("CHECKPOINT_PATH", "s3a://rideshare-checkpoints/"),
        trigger_interval=os.environ.get("TRIGGER_INTERVAL", "10 seconds"),
    )

    error_handler = ErrorHandler(dlq_table_path="s3a://rideshare-bronze/dlq/")

    job = BronzeIngestionLowVolume(spark, kafka_config, checkpoint_config, error_handler)
    query = job.start()
    query.awaitTermination()
