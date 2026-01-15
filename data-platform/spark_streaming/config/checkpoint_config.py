"""Checkpoint management configuration for streaming jobs."""

from dataclasses import dataclass


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint management in streaming jobs."""

    checkpoint_path: str
    checkpoint_interval_seconds: int = 60
    trigger_interval: str = "10 seconds"
    enable_idempotent_writes: bool = True

    def __post_init__(self):
        if not self.checkpoint_path:
            raise ValueError("checkpoint_path must not be empty")

    def to_write_options(self) -> dict:
        """Generate Spark writeStream options for checkpointing."""
        return {
            "checkpointLocation": self.checkpoint_path,
        }
