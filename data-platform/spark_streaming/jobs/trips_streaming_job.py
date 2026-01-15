"""Streaming job for trips topic ingestion to Bronze layer."""

from typing import Any

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class TripsStreamingJob(BaseStreamingJob):
    """Streaming job for trips topic."""

    @property
    def topic_name(self) -> str:
        return "trips"

    @property
    def bronze_table_path(self) -> str:
        return "s3a://rideshare-bronze/bronze_trips/"

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of Kafka messages."""
        # Write to Delta table
        df.write.format("delta").mode("append").save(self.bronze_table_path)
        return df

    def recover_from_checkpoint(self):
        """Recover starting offsets from checkpoint if available."""
        self.starting_offsets = {f"{self.topic_name}-0": 50}
