"""Streaming job for high-volume gps_pings topic ingestion to Bronze layer."""

from spark_streaming.jobs.multi_topic_streaming_job import MultiTopicStreamingJob


class BronzeIngestionHighVolume(MultiTopicStreamingJob):
    """Streaming job for gps_pings topic (highest volume).

    This job is isolated from low-volume topics to prevent GPS ping
    volume from causing backpressure. Handles 8 partitions in dev,
    32 partitions in production.
    """

    def get_topic_names(self) -> list[str]:
        """Return the high-volume topic."""
        return ["gps_pings"]


if __name__ == "__main__":
    import os
    from pyspark.sql import SparkSession
    from spark_streaming.config.kafka_config import KafkaConfig
    from spark_streaming.config.checkpoint_config import CheckpointConfig
    from spark_streaming.utils.error_handler import ErrorHandler

    spark = (
        SparkSession.builder.appName("BronzeIngestionHighVolume")
        .master("local[2]")
        .config("spark.executor.memory", "768m")
        .config("spark.driver.memory", "768m")
        .getOrCreate()
    )

    kafka_config = KafkaConfig(
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
        schema_registry_url=os.environ.get(
            "SCHEMA_REGISTRY_URL", "http://schema-registry:8081"
        ),
    )
    checkpoint_config = CheckpointConfig(
        checkpoint_path=os.environ.get(
            "CHECKPOINT_PATH", "s3a://rideshare-checkpoints/gps_pings/"
        ),
        trigger_interval=os.environ.get("TRIGGER_INTERVAL", "10 seconds"),
    )
    error_handler = ErrorHandler(dlq_table_path="s3a://rideshare-bronze/dlq_gps_pings/")

    job = BronzeIngestionHighVolume(
        spark, kafka_config, checkpoint_config, error_handler
    )
    query = job.start()
    query.awaitTermination()
