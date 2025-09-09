"""Surge pricing event handler with pass-through logic."""

import json
import logging

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class SurgeHandler(BaseHandler):
    """Handler for surge pricing events.

    Pass-through handler that immediately emits surge pricing updates
    to Redis. Pricing changes are critical and should not be aggregated.
    """

    def __init__(self):
        """Initialize surge handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a surge pricing event message.

        Immediately emits to the surge-updates channel.

        Args:
            message: Raw surge event message bytes.

        Returns:
            List with single (channel, event) tuple.
        """
        try:
            event = json.loads(message)
            self.messages_processed += 1

            # Emit immediately to surge-updates channel
            return [("surge-updates", event)]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse surge event: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing surge event: {e}")
            return []

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for surge events."""
        return []
