"""Trip event handler with pass-through logic."""

import json
import logging

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class TripHandler(BaseHandler):
    """Handler for trip events.

    Pass-through handler that immediately emits trip events to Redis.
    Trip state changes are critical and should not be aggregated.
    """

    def __init__(self):
        """Initialize trip handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a trip event message.

        Immediately emits to the trip-updates channel.

        Args:
            message: Raw trip event message bytes.

        Returns:
            List with single (channel, event) tuple.
        """
        try:
            event = json.loads(message)
            self.messages_processed += 1

            # Emit immediately to trip-updates channel
            return [("trip-updates", event)]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse trip event: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing trip event: {e}")
            return []

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for trip events."""
        return []
