"""Streaming job for gps-pings topic ingestion to Bronze layer."""

from typing import Any, Optional
from pyspark.sql.functions import date_format, col

from spark_streaming.framework.base_streaming_job import BaseStreamingJob


class GpsPingsStreamingJob(BaseStreamingJob):
    """Streaming job for gps-pings topic (highest volume)."""

    @property
    def topic_name(self) -> str:
        return "gps-pings"

    @property
    def bronze_table_path(self) -> str:
        return "s3a://rideshare-bronze/bronze_gps_pings/"

    @property
    def partition_columns(self) -> Optional[list]:
        return ["_ingestion_date"]

    def process_batch(self, df: Any, batch_id: int) -> Any:
        """Process a micro-batch of GPS ping messages."""
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
