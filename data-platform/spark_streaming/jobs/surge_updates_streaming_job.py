"""Streaming job for surge-updates topic ingestion to Bronze layer."""

from typing import Any

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class SurgeUpdatesStreamingJob(BaseStreamingJob):
    """Streaming job for surge-updates topic."""

    @property
    def topic_name(self) -> str:
        return "surge-updates"

    @property
    def bronze_table_path(self) -> str:
        return "s3a://rideshare-bronze/bronze_surge_updates/"

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of Kafka messages."""
        df.write.format("delta").mode("append").save(self.bronze_table_path)
        return df

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available."""
        self.starting_offsets = {f"{self.topic_name}-0": 50}
