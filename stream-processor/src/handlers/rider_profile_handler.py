"""Rider profile event handler with pass-through logic."""

import json
import logging

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class RiderProfileHandler(BaseHandler):
    """Handler for rider profile events.

    Pass-through handler that immediately emits rider creation/update events
    to Redis. These are important for real-time visualization of new riders.
    """

    def __init__(self):
        """Initialize rider profile handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a rider profile event message.

        Immediately emits to the rider-updates channel.

        Args:
            message: Raw rider profile event message bytes.

        Returns:
            List with single (channel, event) tuple.
        """
        try:
            event = json.loads(message)
            self.messages_processed += 1

            # Emit immediately to rider-updates channel
            return [("rider-updates", event)]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse rider profile event: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing rider profile event: {e}")
            return []

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for rider profile events."""
        return []
