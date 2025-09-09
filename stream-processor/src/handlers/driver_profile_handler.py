"""Driver profile event handler with pass-through logic."""

import json
import logging

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class DriverProfileHandler(BaseHandler):
    """Handler for driver profile events.

    Pass-through handler that immediately emits driver creation/update events
    to Redis. These are important for real-time visualization of new drivers.
    """

    def __init__(self):
        """Initialize driver profile handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a driver profile event message.

        Immediately emits to the driver-updates channel.

        Args:
            message: Raw driver profile event message bytes.

        Returns:
            List with single (channel, event) tuple.
        """
        try:
            event = json.loads(message)
            self.messages_processed += 1

            # Emit immediately to driver-updates channel
            return [("driver-updates", event)]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse driver profile event: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing driver profile event: {e}")
            return []

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for driver profile events."""
        return []
