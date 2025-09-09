"""Driver status event handler with pass-through logic."""

import json
import logging

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class DriverStatusHandler(BaseHandler):
    """Handler for driver status events.

    Pass-through handler that immediately emits driver status changes
    to Redis. Status changes are important and should not be aggregated.
    """

    def __init__(self):
        """Initialize driver status handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a driver status event message.

        Immediately emits to the driver-updates channel.

        Args:
            message: Raw driver status event message bytes.

        Returns:
            List with single (channel, event) tuple.
        """
        try:
            event = json.loads(message)
            self.messages_processed += 1

            # Emit immediately to driver-updates channel
            return [("driver-updates", event)]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse driver status event: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing driver status event: {e}")
            return []

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for driver status events."""
        return []
