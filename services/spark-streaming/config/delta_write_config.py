"""Configuration for Delta Lake write options in streaming jobs."""

from dataclasses import dataclass, field


@dataclass
class DeltaWriteConfig:
    """Configuration for Delta Lake write options in streaming jobs.

    This class controls write-time optimizations to reduce small files:
    - Auto-optimize settings (optimize write, auto compact, target file size)
    - Coalesce settings to reduce partition count before write

    Attributes:
        optimize_write: Enable Delta Lake optimized writes to reduce small files.
        auto_compact: Enable automatic compaction of small files after writes.
        target_file_size_mb: Target file size in MB for optimized writes.
        default_coalesce_partitions: Default number of partitions to coalesce to.
        topic_coalesce_overrides: Per-topic overrides for coalesce partition count.
    """

    # Auto-optimize settings
    optimize_write: bool = True
    auto_compact: bool = True
    target_file_size_mb: int = 128

    # Coalesce settings
    default_coalesce_partitions: int = 1
    topic_coalesce_overrides: dict[str, int] = field(default_factory=dict)

    def get_coalesce_partitions(self, topic: str) -> int:
        """Get coalesce partition count for a specific topic.

        Args:
            topic: Kafka topic name.

        Returns:
            Number of partitions to coalesce to for this topic.
        """
        return self.topic_coalesce_overrides.get(topic, self.default_coalesce_partitions)

    def to_write_options(self) -> dict[str, str]:
        """Generate Delta Lake write options dictionary.

        Returns:
            Dictionary of Delta Lake write options suitable for DataFrame.write.option().

        Note:
            Delta Lake 4.0 removed support for delta.targetFileSize as a write option.
            File size optimization is handled by optimizeWrite using Spark's default
            target size (typically 128MB). Use spark.databricks.delta.optimizeWrite.fileSize
            SparkConf to override if needed.
        """
        return {
            "delta.autoOptimize.optimizeWrite": str(self.optimize_write).lower(),
            "delta.autoOptimize.autoCompact": str(self.auto_compact).lower(),
        }
