"""Base handler interface for stream processing."""

from abc import ABC, abstractmethod


class BaseHandler(ABC):
    """Abstract base class for event handlers.

    Handlers process Kafka messages and produce (channel, event) tuples
    for publishing to Redis. Handlers can be:
    - Pass-through: Immediately emit events to Redis
    - Windowed: Buffer events and emit aggregated results on flush
    """

    @abstractmethod
    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a single Kafka message.

        Args:
            message: Raw message bytes from Kafka.

        Returns:
            List of (channel, event) tuples to publish to Redis.
            Empty list if buffering for later flush.
        """
        pass

    @abstractmethod
    def flush(self) -> list[tuple[str, dict]]:
        """Flush any buffered state.

        Called periodically (e.g., every window_size_ms) to emit
        aggregated events.

        Returns:
            List of (channel, event) tuples to publish to Redis.
            Empty list if nothing buffered.
        """
        pass

    @property
    def is_windowed(self) -> bool:
        """Return True if this handler uses windowed aggregation."""
        return False
