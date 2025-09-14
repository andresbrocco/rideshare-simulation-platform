"""GPS ping handler with windowed aggregation."""

import json
import logging
from collections import defaultdict

from pydantic import ValidationError

from ..events.schemas import GPSPingEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class GPSHandler(BaseHandler):
    """Handler for GPS ping events with windowed aggregation.

    Aggregates GPS pings within time windows, keeping only the latest
    position per entity (driver/rider). This dramatically reduces the
    message rate to the frontend.

    Strategies:
    - "latest": Keep only the most recent GPS ping per entity
    - "sample": Keep every Nth GPS ping per entity
    """

    def __init__(
        self,
        window_size_ms: int = 100,
        strategy: str = "latest",
        sample_rate: int = 10,
    ):
        """Initialize GPS handler.

        Args:
            window_size_ms: Window duration in milliseconds.
            strategy: "latest" or "sample".
            sample_rate: For sample strategy, emit every Nth message.
        """
        self.window_size_ms = window_size_ms
        self.strategy = strategy
        self.sample_rate = sample_rate

        # Window state: entity_id -> latest GPS event
        self.window_state: dict[str, dict] = {}

        # For sampling strategy: entity_id -> message counter
        self.sample_counters: dict[str, int] = defaultdict(int)

        # Metrics
        self.messages_received = 0
        self.messages_emitted = 0

    @property
    def is_windowed(self) -> bool:
        """GPS handler uses windowed aggregation."""
        return True

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a GPS ping message."""
        try:
            raw = json.loads(message)
            validated = GPSPingEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"GPS validation error: {e}")
            get_metrics_collector().record_validation_error("gps")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse GPS event: {e}")
            get_metrics_collector().record_validation_error("gps")
            return []

        entity_id = event.get("entity_id")
        self.messages_received += 1

        if self.strategy == "latest":
            self.window_state[entity_id] = event
            return []
        elif self.strategy == "sample":
            self.sample_counters[entity_id] += 1
            if self.sample_counters[entity_id] >= self.sample_rate:
                self.sample_counters[entity_id] = 0
                self.window_state[entity_id] = event
            return []

        return []

    def flush(self) -> list[tuple[str, dict]]:
        """Flush the current window and return aggregated events.

        Returns:
            List of (channel, event) tuples for all entities in window.
        """
        if not self.window_state:
            return []

        results: list[tuple[str, dict]] = []

        for entity_id, event in self.window_state.items():
            entity_type = event.get("entity_type", "driver")

            # Route to appropriate Redis channel
            if entity_type == "driver":
                channel = "driver-updates"
            elif entity_type == "rider":
                channel = "rider-updates"
            else:
                channel = "driver-updates"  # Default to driver

            results.append((channel, event))
            self.messages_emitted += 1

        # Clear window state
        entity_count = len(self.window_state)
        self.window_state.clear()

        if entity_count > 0:
            logger.debug(
                f"Flushed GPS window: {entity_count} entities, "
                f"total received: {self.messages_received}, "
                f"total emitted: {self.messages_emitted}"
            )

        return results

    def get_aggregation_ratio(self) -> float:
        """Return the message reduction ratio."""
        if self.messages_emitted == 0:
            return 0.0
        return self.messages_received / self.messages_emitted
