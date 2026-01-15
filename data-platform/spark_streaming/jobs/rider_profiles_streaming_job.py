"""Streaming job for rider-profiles topic ingestion to Bronze layer."""

from typing import Any

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class RiderProfilesStreamingJob(BaseStreamingJob):
    """Streaming job for rider-profiles topic."""

    @property
    def topic_name(self) -> str:
        return "rider-profiles"

    @property
    def bronze_table_path(self) -> str:
        return "s3a://rideshare-bronze/bronze_rider_profiles/"

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of Kafka messages."""
        df.write.format("delta").mode("append").save(self.bronze_table_path)
        return df

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available."""
        self.starting_offsets = {f"{self.topic_name}-0": 50}
